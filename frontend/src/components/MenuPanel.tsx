import { useState } from "react";
import type { Menu, MenuItem, SelectedOption } from "../types";

interface MenuPanelProps {
  menu: Menu | null;
  menuError: string | null;
  connected: boolean;
  onAddToOrder: (item: MenuItem, quantity: number, selections: SelectedOption[]) => void;
}

export function MenuPanel({ menu, menuError, connected, onAddToOrder }: MenuPanelProps) {
  if (menuError) {
    return (
      <div className="panel menu-panel">
        <p className="error-text">Couldn't load the menu: {menuError}</p>
      </div>
    );
  }

  if (!menu) {
    return (
      <div className="panel menu-panel">
        <p className="muted-text">Loading menu…</p>
      </div>
    );
  }

  return (
    <div className="panel menu-panel">
      {menu.categories.map((category) => (
        <section key={category.id} className="menu-category">
          <h2>{category.name}</h2>
          <div className="menu-items">
            {category.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                connected={connected}
                onAddToOrder={onAddToOrder}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function ItemCard({
  item,
  connected,
  onAddToOrder,
}: {
  item: MenuItem;
  connected: boolean;
  onAddToOrder: (item: MenuItem, quantity: number, selections: SelectedOption[]) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [quantity, setQuantity] = useState(1);
  // groupId -> chosen options
  const [selectionsByGroup, setSelectionsByGroup] = useState<Record<string, SelectedOption[]>>({});

  const groups = item.customization_groups;

  function setGroupSelection(groupId: string, next: SelectedOption[]) {
    setSelectionsByGroup((prev) => ({ ...prev, [groupId]: next }));
  }

  function toggleCheckboxOption(
    group: MenuItem["customization_groups"][number],
    optionId: string,
    optionName: string,
    priceDelta: number,
  ) {
    const current = selectionsByGroup[group.id] ?? [];
    const already = current.some((o) => o.optionId === optionId);
    if (already) {
      setGroupSelection(
        group.id,
        current.filter((o) => o.optionId !== optionId),
      );
      return;
    }
    if (current.length >= group.max_choices) return;
    setGroupSelection(group.id, [
      ...current,
      { groupId: group.id, groupName: group.name, optionId, optionName, priceDelta },
    ]);
  }

  function setRadioOption(
    group: MenuItem["customization_groups"][number],
    optionId: string,
    optionName: string,
    priceDelta: number,
  ) {
    setGroupSelection(group.id, [
      { groupId: group.id, groupName: group.name, optionId, optionName, priceDelta },
    ]);
  }

  const allSelections = Object.values(selectionsByGroup).flat();
  const missingRequiredGroup = groups.find(
    (g) => g.is_required && (selectionsByGroup[g.id]?.length ?? 0) === 0,
  );
  const canAdd = connected && !missingRequiredGroup && item.is_available;

  const selectedDelta = allSelections.reduce((sum, o) => sum + o.priceDelta, 0);
  const unitPrice = item.price + selectedDelta;

  function handleAdd() {
    if (!canAdd) return;
    onAddToOrder(item, quantity, allSelections);
    setExpanded(false);
    setQuantity(1);
    setSelectionsByGroup({});
  }

  return (
    <div className={`item-card${!item.is_available ? " unavailable" : ""}`}>
      <button
        type="button"
        className="item-card-summary"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        {item.image_url ? (
          <img className="item-thumb" src={item.image_url} alt="" />
        ) : (
          <div className="item-thumb item-thumb-placeholder" aria-hidden="true" />
        )}
        <div className="item-info">
          <span className="item-name">{item.name}</span>
          {item.description && <span className="item-desc">{item.description}</span>}
          {!item.is_available && <span className="item-unavailable-tag">Unavailable</span>}
        </div>
        <span className="item-price">₹{item.price.toFixed(2)}</span>
      </button>

      {expanded && item.is_available && (
        <div className="item-card-expanded">
          {groups.map((group) => (
            <div key={group.id} className="customization-group">
              <div className="customization-group-header">
                <strong>{group.name}</strong>
                <span className="muted-text">
                  {group.is_required ? "required" : "optional"}
                  {group.max_choices > 1 ? ` · pick up to ${group.max_choices}` : ""}
                </span>
              </div>
              <div className="customization-options">
                {group.options.map((option) => {
                  const checked =
                    selectionsByGroup[group.id]?.some((o) => o.optionId === option.id) ?? false;
                  const disabled =
                    !option.is_available ||
                    (group.max_choices > 1 &&
                      !checked &&
                      (selectionsByGroup[group.id]?.length ?? 0) >= group.max_choices);
                  return (
                    <label key={option.id} className={`option-choice${disabled ? " disabled" : ""}`}>
                      <input
                        type={group.max_choices === 1 ? "radio" : "checkbox"}
                        name={`${item.id}-${group.id}`}
                        checked={checked}
                        disabled={disabled}
                        onChange={() =>
                          group.max_choices === 1
                            ? setRadioOption(group, option.id, option.name, option.price_delta)
                            : toggleCheckboxOption(group, option.id, option.name, option.price_delta)
                        }
                      />
                      <span>
                        {option.name}
                        {option.price_delta ? ` (+₹${option.price_delta.toFixed(2)})` : ""}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="item-card-footer">
            <div className="quantity-stepper">
              <button type="button" onClick={() => setQuantity((q) => Math.max(1, q - 1))}>
                −
              </button>
              <span>{quantity}</span>
              <button type="button" onClick={() => setQuantity((q) => q + 1)}>
                +
              </button>
            </div>
            <button type="button" className="add-to-order-btn" disabled={!canAdd} onClick={handleAdd}>
              {connected
                ? missingRequiredGroup
                  ? `Choose ${missingRequiredGroup.name}`
                  : `Add to order · ₹${(unitPrice * quantity).toFixed(2)}`
                : "Connect to order"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
