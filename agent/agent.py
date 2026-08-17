"""LiveKit voice agent worker — see 03-voice-agent-core.md and 04-order-cart-feature.md.

Joins a room, runs the STT -> LLM -> TTS voice pipeline, answers menu questions and builds up an
in-memory cart via function tools, grounded in GET /menu from the backend. Every cart mutation
publishes a `cart_update` data message so the web frontend's cart panel stays in lock-step with
the spoken conversation. Once the customer confirms, complete_order creates the order on the
backend and publishes an `order_update` data message; the web frontend takes it from there to
show a UPI QR (PayU hosted checkout, restricted to UPI) and carries the order through to
paid/failed on its own. This process ends the call right after the order-confirmation reply
instead of waiting around for payment to resolve.

STT/LLM/TTS/VAD all run through LiveKit Cloud's hosted inference gateway
(`livekit.agents.inference`), authenticated with the same LIVEKIT_URL/LIVEKIT_API_KEY/
LIVEKIT_API_SECRET used to join the room — no separate Deepgram/Cartesia/OpenAI account needed.
"""

import asyncio
import itertools
import json
import logging
import os
from typing import TypedDict

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    inference,
    llm,
)

load_dotenv()

logger = logging.getLogger("qsr-voice-agent")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


class CustomizationChoice(TypedDict):
    group_name: str
    option_name: str


class ConversationRecorder:
    """Persists the conversation to the backend as it happens, so it survives a client-side
    disconnect/refresh and can be pulled up later to debug what actually happened in a session.
    Every write is fire-and-forget and swallows its own errors — recording must never be able to
    break or stall the live voice pipeline."""

    def __init__(self, http_client: httpx.AsyncClient, room_name: str):
        self._client = http_client
        self._room_name = room_name

    async def start(self) -> None:
        try:
            resp = await self._client.post("/conversations", json={"room_name": self._room_name})
            resp.raise_for_status()
        except Exception:
            logger.exception("failed to record conversation session start")

    def record_turn(self, role: str, content: str) -> None:
        asyncio.create_task(self._record_turn(role, content))

    async def _record_turn(self, role: str, content: str) -> None:
        try:
            resp = await self._client.post(
                f"/conversations/{self._room_name}/turns",
                json={"role": role, "content": content},
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("failed to record conversation turn")

    async def end(self) -> None:
        try:
            resp = await self._client.post(f"/conversations/{self._room_name}/end")
            resp.raise_for_status()
        except Exception:
            logger.exception("failed to record conversation session end")


async def fetch_menu() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BACKEND_URL}/menu")
        resp.raise_for_status()
        return resp.json()


def build_system_prompt(menu: dict) -> str:
    lines = [
        "You are a friendly voice ordering assistant at the counter of a quick-service "
        "restaurant (takeaway/counter-pickup only — never ask which table the customer is at).",
        "",
        "Ground rules:",
        "- Only mention items, prices, and customizations that appear in the MENU section below "
        "— never invent an item, price, or customization option.",
        "- This is a spoken conversation, not a chat window: keep responses short. Don't read out "
        "long lists — ask a clarifying question instead (e.g. \"We've got burgers, wraps, and "
        "beverages — what sounds good?\" rather than listing every item).",
        "- Ask ONE thing at a time, then stop and actually wait for their answer — never stack "
        "multiple questions in one turn (e.g. don't ask about size AND add-ons AND drinks "
        "together) and never assume an answer and move on before they've replied. This is a "
        "back-and-forth conversation, not a monologue — leave real room for the customer to talk.",
        "- Use the get_item_details tool to confirm an item's exact name, price, and "
        "customization options before describing them in detail or confirming an order. You "
        "already have the full menu above, so only call it once per item, not repeatedly.",
        "- If you're about to call several tools in a row before you can reply (e.g. looking "
        "something up then adding it), a brief \"one sec\" is fine so they're not met with dead "
        "air — but don't add filler before quick, single tool calls, and never use an "
        "acknowledgement as an excuse to keep talking instead of listening.",
        "- For a customization group marked required, ask the customer to choose an option "
        "before treating the item as fully specified.",
        "- If you can't find an item the customer describes, use get_item_details to check for a "
        "close match and ask them to clarify rather than guessing.",
        "- When the customer indicates they're done ordering (e.g. \"that's all\", \"checkout\", "
        "\"I'm done\"), first call get_cart_summary and read the order back to them (items and "
        "total) so they can confirm it's correct — don't call complete_order until they confirm.",
        "- Once they confirm, call complete_order. This creates their order and puts a UPI QR "
        "code on their screen. In the same reply: tell them their total, ask them to scan the QR "
        "code on screen with any UPI app to pay, mention their pickup code and receipt will show "
        "on screen once payment goes through (or that staff can take payment at the counter if it "
        "doesn't), and say goodbye — this reply is the last thing you say, the call ends right "
        "after it, so don't say you'll wait or check back.",
        "- Don't call complete_order for an empty cart — if they try to check out with nothing in "
        "the cart, ask what they'd like to order instead. If complete_order returns "
        "{\"status\": \"order_already_placed\"}, don't create another order — just let them know "
        "their order is already placed and waiting on payment.",
        "",
        "MENU:",
    ]
    for category in menu.get("categories", []):
        lines.append(f"\n{category['name']}:")
        for item in category.get("items", []):
            lines.append(
                f"- {item['name']} (₹{item['price']}): {item.get('description') or ''}"
            )
            for group in item.get("customization_groups", []):
                requirement = "required" if group["is_required"] else "optional"
                pick = "pick 1" if group["max_choices"] == 1 else f"pick up to {group['max_choices']}"
                opts = ", ".join(
                    f"{o['name']} (+₹{o['price_delta']})" if o["price_delta"] else o["name"]
                    for o in group.get("options", [])
                )
                lines.append(f"    {group['name']} ({requirement}, {pick}): {opts}")
    return "\n".join(lines)


class MenuAgent(Agent):
    def __init__(self, menu: dict, room: rtc.Room, job_ctx: JobContext, http_client: httpx.AsyncClient):
        self._menu = menu
        self._room = room
        self._job_ctx = job_ctx
        self._client = http_client
        self._cart: list[dict] = []
        self._line_id_seq = itertools.count(1)
        # Set once complete_order successfully creates an order — the cart is frozen from then
        # on (checkout is in flight against a specific priced snapshot) until payment resolves
        # and the call ends.
        self._order_id: str | None = None
        self._pickup_token: str | None = None
        super().__init__(instructions=build_system_prompt(menu))

    def _all_items(self) -> list[dict]:
        return [
            item
            for category in self._menu.get("categories", [])
            for item in category.get("items", [])
        ]

    def _find_item(self, item_name: str) -> dict | None:
        needle = item_name.strip().lower()
        items = self._all_items()
        for item in items:
            if item["name"].strip().lower() == needle:
                return item
        matches = [item for item in items if needle in item["name"].strip().lower()]
        if len(matches) == 1:
            return matches[0]
        return None

    @function_tool()
    async def get_menu(self, context: RunContext) -> dict:
        """Return the full current menu: categories, items, prices, descriptions, and
        customization groups/options. Prefer answering from context you already have; call this
        only if you need to re-check something."""
        return self._menu

    @function_tool()
    async def get_item_details(self, context: RunContext, item_name: str) -> dict:
        """Look up a single menu item by name (exact or partial match) and return its price,
        description, and customization groups/options. Use this before confirming an item to the
        customer, or when their description doesn't clearly match one item. Returns
        {"found": false} if no unambiguous match exists — in that case, ask the customer to
        clarify which item they mean rather than guessing."""
        item = self._find_item(item_name)
        if item is None:
            return {"found": False}
        return {"found": True, "item": item}

    # --- cart (04-order-cart-feature.md) -------------------------------------------------

    def _price_customizations(
        self, item: dict, customizations: list[CustomizationChoice]
    ) -> tuple[list[dict], float] | dict:
        """Validate a requested customization selection against an item's groups/options.

        Returns (priced_customizations, price_delta_total) on success, or a structured
        {"error": ...} dict on the first validation failure — the LLM should turn that into a
        clarifying question rather than guessing a default.
        """
        groups_by_name = {g["name"].strip().lower(): g for g in item.get("customization_groups", [])}

        chosen_by_group: dict[str, list[dict]] = {}
        for choice in customizations:
            group_name = choice.get("group_name", "")
            option_name = choice.get("option_name", "")
            group = groups_by_name.get(group_name.strip().lower())
            if group is None:
                return {"error": "unknown_group", "group_name": group_name}
            option = next(
                (o for o in group["options"] if o["name"].strip().lower() == option_name.strip().lower()),
                None,
            )
            if option is None:
                return {
                    "error": "option_not_found",
                    "group_name": group["name"],
                    "option_name": option_name,
                }
            if not option["is_available"]:
                return {
                    "error": "option_unavailable",
                    "group_name": group["name"],
                    "option_name": option["name"],
                }
            chosen_by_group.setdefault(group["name"], []).append(option)

        for group in item.get("customization_groups", []):
            selected = chosen_by_group.get(group["name"], [])
            if group["is_required"] and not selected:
                return {"error": "missing_required_group", "group_name": group["name"]}
            if len(selected) > group["max_choices"]:
                return {
                    "error": "too_many_choices",
                    "group_name": group["name"],
                    "max_choices": group["max_choices"],
                }

        priced: list[dict] = []
        price_delta_total = 0.0
        for group_name, options in chosen_by_group.items():
            for option in options:
                priced.append(
                    {
                        "group_name": group_name,
                        "option_name": option["name"],
                        "price_delta": option["price_delta"],
                    }
                )
                price_delta_total += option["price_delta"]

        return priced, price_delta_total

    def _recompute_subtotal(self) -> float:
        return round(sum(line["line_total"] for line in self._cart), 2)

    def _cart_summary(self) -> dict:
        return {"items": self._cart, "subtotal": self._recompute_subtotal()}

    async def _publish_cart_update(self) -> None:
        payload = json.dumps({"type": "cart_update", "cart": self._cart_summary()})
        await self._room.local_participant.publish_data(payload, reliable=True, topic="cart_update")

    def _find_line(self, line_id: int) -> dict | None:
        return next((line for line in self._cart if line["line_id"] == line_id), None)

    # These _impl methods hold the actual cart mutation logic and are shared by two entry
    # points: the @function_tool wrappers below (LLM/voice-driven, via RunContext) and the RPC
    # handlers registered in entrypoint() (UI tap-driven, bypassing the LLM entirely for a
    # realtime add/remove/update feel). Both publish the same cart_update data message.

    async def _add_to_cart_impl(
        self,
        item_name: str,
        quantity: int,
        customizations: list[CustomizationChoice] | None,
    ) -> dict:
        if self._order_id is not None:
            return {"error": "order_already_placed"}
        customizations = customizations or []

        item = self._find_item(item_name)
        if item is None:
            return {"error": "item_not_found", "item_name": item_name}
        if not item["is_available"]:
            return {"error": "item_unavailable", "item_name": item["name"]}
        if quantity < 1:
            return {"error": "invalid_quantity", "quantity": quantity}

        result = self._price_customizations(item, customizations)
        if isinstance(result, dict):
            return result
        priced_customizations, price_delta_total = result
        unit_price = round(item["price"] + price_delta_total, 2)

        existing = next(
            (
                line
                for line in self._cart
                if line["menu_item_id"] == item["id"]
                and line["customizations"] == priced_customizations
            ),
            None,
        )
        if existing is not None:
            existing["quantity"] += quantity
            existing["line_total"] = round(existing["unit_price"] * existing["quantity"], 2)
        else:
            self._cart.append(
                {
                    "line_id": next(self._line_id_seq),
                    "menu_item_id": item["id"],
                    "name": item["name"],
                    "quantity": quantity,
                    "customizations": priced_customizations,
                    "unit_price": unit_price,
                    "line_total": round(unit_price * quantity, 2),
                }
            )

        await self._publish_cart_update()
        return self._cart_summary()

    async def _update_cart_item_impl(
        self,
        line_id: int,
        quantity: int | None,
        customizations: list[CustomizationChoice] | None,
    ) -> dict:
        if self._order_id is not None:
            return {"error": "order_already_placed"}
        line = self._find_line(line_id)
        if line is None:
            return {"error": "line_not_found", "line_id": line_id}

        item = self._find_item(line["name"])
        if item is None:
            return {"error": "item_not_found", "item_name": line["name"]}

        if customizations is not None:
            result = self._price_customizations(item, customizations)
            if isinstance(result, dict):
                return result
            priced_customizations, price_delta_total = result
            line["customizations"] = priced_customizations
            line["unit_price"] = round(item["price"] + price_delta_total, 2)

        if quantity is not None:
            if quantity < 1:
                return {"error": "invalid_quantity", "quantity": quantity}
            line["quantity"] = quantity

        line["line_total"] = round(line["unit_price"] * line["quantity"], 2)

        await self._publish_cart_update()
        return self._cart_summary()

    async def _remove_from_cart_impl(self, line_id: int) -> dict:
        if self._order_id is not None:
            return {"error": "order_already_placed"}
        line = self._find_line(line_id)
        if line is None:
            return {"error": "line_not_found", "line_id": line_id}

        self._cart.remove(line)
        await self._publish_cart_update()
        return self._cart_summary()

    @function_tool()
    async def add_to_cart(
        self,
        context: RunContext,
        item_name: str,
        quantity: int,
        customizations: list[CustomizationChoice] | None = None,
    ) -> dict:
        """Add an item to the cart. `customizations` is a list of
        {"group_name": str, "option_name": str} picks, one entry per chosen option (e.g. two
        entries for two add-ons). Validates the item exists and is available, that every required
        customization group has a selection, and that no group exceeds its max_choices. On
        validation failure returns a structured {"error": ...} — ask the customer a clarifying
        question rather than guessing a default. On success returns the updated cart summary."""
        return await self._add_to_cart_impl(item_name, quantity, customizations)

    @function_tool()
    async def update_cart_item(
        self,
        context: RunContext,
        line_id: int,
        quantity: int | None = None,
        customizations: list[CustomizationChoice] | None = None,
    ) -> dict:
        """Update an existing cart line's quantity and/or customizations (same shape/validation
        as add_to_cart). Only fields provided are changed. Returns {"error": "line_not_found"} if
        line_id doesn't match a current cart line — call get_cart_summary first if unsure of the
        current line_ids. Returns the updated cart summary on success."""
        return await self._update_cart_item_impl(line_id, quantity, customizations)

    @function_tool()
    async def remove_from_cart(self, context: RunContext, line_id: int) -> dict:
        """Remove a line from the cart by line_id. Returns {"error": "line_not_found"} if it
        doesn't match a current cart line. Returns the updated cart summary on success (an empty
        cart is a valid, still-published result)."""
        return await self._remove_from_cart_impl(line_id)

    @function_tool()
    async def get_cart_summary(self, context: RunContext) -> dict:
        """Return the current cart: line items (with quantities, customizations, line totals) and
        the subtotal. Call this before verbally confirming the order back to the customer, and
        before checkout."""
        return self._cart_summary()

    async def _publish_order_update(self, msg_type: str, order: dict) -> None:
        payload = json.dumps({"type": msg_type, "order": order})
        await self._room.local_participant.publish_data(payload, reliable=True, topic="order_update")

    @function_tool()
    async def complete_order(self, context: RunContext) -> dict:
        """Call this once the customer has confirmed their order is correct and they're ready to
        pay. Creates the order on the backend and puts a UPI QR code on their screen for payment.
        The message you give right after this call is the LAST thing you say — tell them their
        total, ask them to scan the QR code on screen to pay, mention their pickup code and
        receipt will appear on screen once payment goes through (or that staff can take payment
        at the counter if it doesn't), and say goodbye. The call ends automatically right after
        you finish speaking, so don't say you'll wait or check back.
        Returns {"error": "cart_empty"} if the cart has nothing in it — don't call this for an
        empty cart. Returns {"status": "order_already_placed", ...} if an order was already
        created this call — don't create a second one, just relay the existing status. On success
        returns {"order_id", "pickup_token", "total", "status": "pending_payment"}."""
        if self._order_id is not None:
            return {
                "status": "order_already_placed",
                "order_id": self._order_id,
                "pickup_token": self._pickup_token,
            }
        if not self._cart:
            return {"error": "cart_empty"}

        subtotal = self._recompute_subtotal()
        items = [
            {
                "menu_item_id": line["menu_item_id"],
                "name": line["name"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"],
                "customizations": line["customizations"],
            }
            for line in self._cart
        ]
        try:
            resp = await self._client.post(
                "/orders",
                json={
                    "room_name": self._room.name,
                    "items": items,
                    "subtotal": subtotal,
                    "total": subtotal,
                },
            )
            resp.raise_for_status()
            order = resp.json()
        except Exception:
            logger.exception("failed to create order")
            return {"error": "order_creation_failed"}

        self._order_id = order["id"]
        self._pickup_token = order["pickup_token"]

        await self._publish_order_update(
            "order_created",
            {
                "id": order["id"],
                "pickup_token": order["pickup_token"],
                "total": order["total"],
                "status": order["status"],
            },
        )
        asyncio.create_task(self._end_call_after_speech(context.speech_handle))
        return {
            "order_id": order["id"],
            "pickup_token": order["pickup_token"],
            "total": order["total"],
            "status": order["status"],
        }

    async def _end_call_after_speech(self, speech_handle) -> None:
        """Runs in the background after complete_order's confirmation reply. Payment resolution
        (paid/failed) and the pickup-code readout now happen entirely on screen — the checkout
        panel polls the backend directly (see backend/app/routers/payments.py's surl/furl
        callback) — so the room is torn down right after the confirmation line finishes instead
        of staying connected while the agent polls for payment to resolve, which otherwise kept
        billing for up to 180s per order for no UX benefit."""
        try:
            await speech_handle.wait_for_playout()
        except Exception:
            logger.exception("error waiting for closing speech to finish")
        await asyncio.sleep(0.8)  # small buffer so the tail of the goodbye isn't cut off
        # room.disconnect() would only remove the agent's own participant — the customer would
        # be left connected with a dangling session. delete_room() tears down the whole room and
        # disconnects everyone, which is what "closing the voice loop" means end-to-end.
        await self._job_ctx.delete_room()

    def register_cart_rpc_methods(self) -> None:
        """Expose direct RPC entry points for the web UI's tap-to-add/remove/adjust controls, so
        those interactions mutate the cart and publish cart_update immediately instead of waiting
        on an LLM conversational turn (which is what the voice/chat function-tool path above
        does). Both paths mutate the same in-memory cart and publish the same data message, so
        the LLM's view of the cart (via get_cart_summary) always reflects UI-driven changes too.
        """
        local = self._room.local_participant

        async def handle_add(data: rtc.RpcInvocationData) -> str:
            try:
                args = json.loads(data.payload)
                result = await self._add_to_cart_impl(
                    item_name=args["item_name"],
                    quantity=int(args.get("quantity", 1)),
                    customizations=args.get("customizations"),
                )
            except (KeyError, ValueError, TypeError) as exc:
                result = {"error": "invalid_payload", "detail": str(exc)}
            return json.dumps(result)

        async def handle_update(data: rtc.RpcInvocationData) -> str:
            try:
                args = json.loads(data.payload)
                result = await self._update_cart_item_impl(
                    line_id=int(args["line_id"]),
                    quantity=int(args["quantity"]) if "quantity" in args and args["quantity"] is not None else None,
                    customizations=args.get("customizations"),
                )
            except (KeyError, ValueError, TypeError) as exc:
                result = {"error": "invalid_payload", "detail": str(exc)}
            return json.dumps(result)

        async def handle_remove(data: rtc.RpcInvocationData) -> str:
            try:
                args = json.loads(data.payload)
                result = await self._remove_from_cart_impl(line_id=int(args["line_id"]))
            except (KeyError, ValueError, TypeError) as exc:
                result = {"error": "invalid_payload", "detail": str(exc)}
            return json.dumps(result)

        local.register_rpc_method("cart.add", handle_add)
        local.register_rpc_method("cart.update", handle_update)
        local.register_rpc_method("cart.remove", handle_remove)


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # complete_order tears the room down itself once an order is placed (see
    # _end_call_after_speech), but a customer who refreshes/closes the tab mid-conversation
    # never triggers that path — they just vanish, leaving this job alone in the room, still
    # running the STT/LLM/TTS pipeline and waiting on speech that will never come. LiveKit's own
    # empty-room timeout can't be relied on here since the agent itself remains a participant, so
    # close the room ourselves as soon as the customer is the only one who left.
    def _on_participant_disconnected(_participant: rtc.RemoteParticipant) -> None:
        if ctx.room.remote_participants:
            return
        logger.info("customer left room %s with no order placed; tearing it down", ctx.room.name)

        async def _close_abandoned_room() -> None:
            try:
                await ctx.delete_room()
            except Exception:
                # Already being torn down by the complete_order path racing with this, or the
                # room is simply gone by the time this runs — either way, nothing left to do.
                logger.exception("failed to delete abandoned room %s", ctx.room.name)

        asyncio.create_task(_close_abandoned_room())

    ctx.room.on("participant_disconnected", _on_participant_disconnected)

    menu = await fetch_menu()
    logger.info("Fetched menu: %d categories", len(menu.get("categories", [])))

    # Long-lived for the whole job, not scoped to this function — entrypoint() returns as soon
    # as the initial greeting is queued, while the framework keeps the session running via its
    # own background tasks. add_shutdown_callback (below) is what actually closes this.
    http_client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0)
    recorder = ConversationRecorder(http_client, ctx.room.name)
    await recorder.start()

    async def _on_shutdown(reason: str) -> None:
        await recorder.end()
        await http_client.aclose()

    ctx.add_shutdown_callback(_on_shutdown)

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(model="openai/gpt-4o-mini"),
        tts=inference.TTS(model="cartesia/sonic-2"),  # uses the model's default voice
        vad=inference.VAD(),
        # preemptive_tts (tried earlier) synthesizes audio before the turn is even confirmed
        # complete, which made the agent jump in over the customer / not leave room for them to
        # reply — reverted to the default (LLM-only preemption, no early audio). Endpointing
        # delay is also nudged up slightly so a customer's mid-sentence pause isn't mistaken for
        # the end of their turn.
        turn_handling={"endpointing": {"min_delay": 0.7}},
    )

    def _on_conversation_item(ev) -> None:
        item = ev.item
        if not isinstance(item, llm.ChatMessage):
            return
        text = item.text_content
        if not text:
            return
        recorder.record_turn(item.role, text)

    session.on("conversation_item_added", _on_conversation_item)

    agent = MenuAgent(menu, room=ctx.room, job_ctx=ctx, http_client=http_client)
    agent.register_cart_rpc_methods()

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(
        instructions=(
            "Proactively greet the customer right away — don't wait for them to speak first. "
            "Keep it warm and brief, then ask what they'd like to have today. "
            "Don't list the whole menu unprompted."
        )
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
