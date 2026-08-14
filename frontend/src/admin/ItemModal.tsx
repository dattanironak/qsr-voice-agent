import { useEffect, useState } from "react";
import type { CustomizationGroup, MenuCategory, MenuItem } from "../types";
import {
  createGroup,
  createItem,
  createOption,
  deleteGroup,
  deleteOption,
  updateGroup,
  updateItem,
  updateOption,
  uploadImage,
} from "./api";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

interface ItemModalProps {
  categories: MenuCategory[];
  categoryId: string;
  item: MenuItem | null;
  onClose: () => void;
  onChanged: () => Promise<void>;
  onCreated: (item: MenuItem) => void;
}

export function ItemModal({ categories, categoryId, item, onClose, onChanged, onCreated }: ItemModalProps) {
  const isEditing = item !== null;

  const [name, setName] = useState(item?.name ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [price, setPrice] = useState(item ? String(item.price) : "");
  const [imageUrl, setImageUrl] = useState(item?.image_url ?? "");
  const [isAvailable, setIsAvailable] = useState(item?.is_available ?? true);
  const [selectedCategoryId, setSelectedCategoryId] = useState(categoryId);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    setName(item?.name ?? "");
    setDescription(item?.description ?? "");
    setPrice(item ? String(item.price) : "");
    setImageUrl(item?.image_url ?? "");
    setIsAvailable(item?.is_available ?? true);
    setSelectedCategoryId(categoryId);
    setUploadError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.id]);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const { url } = await uploadImage(file);
      setImageUrl(url);
    } catch (err) {
      setUploadError(errorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    const parsedPrice = Number(price);
    if (!trimmedName) {
      setError("Name is required");
      return;
    }
    if (Number.isNaN(parsedPrice) || parsedPrice < 0) {
      setError("Price must be a non-negative number");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const data = {
        name: trimmedName,
        description: description.trim() || null,
        price: parsedPrice,
        is_available: isAvailable,
        image_url: imageUrl.trim() || null,
        sort_order: item?.sort_order ?? 0,
      };
      if (isEditing && item) {
        const updated = await updateItem(item.id, {
          ...data,
          ...(selectedCategoryId !== categoryId ? { category_id: selectedCategoryId } : {}),
        });
        await onChanged();
        onCreated(updated);
      } else {
        const created = await createItem(selectedCategoryId, data);
        await onChanged();
        onCreated(created);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-modal-backdrop" onClick={onClose}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <div className="admin-modal-header">
          <h2>{isEditing ? "Edit item" : "New item"}</h2>
          <button type="button" className="admin-icon-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <form className="admin-form" onSubmit={handleSave}>
          <label className="admin-field">
            <span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>

          <label className="admin-field">
            <span>Description</span>
            <textarea
              rows={2}
              value={description ?? ""}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>

          <div className="admin-field-row">
            <label className="admin-field">
              <span>Price (₹)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
              />
            </label>

            <label className="admin-field">
              <span>Category</span>
              <select
                value={selectedCategoryId}
                onChange={(e) => setSelectedCategoryId(e.target.value)}
              >
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="admin-field">
            <span>Image</span>
            <div className="admin-image-field">
              {imageUrl && <img className="admin-image-preview" src={imageUrl} alt="" />}
              <div className="admin-image-controls">
                <input
                  placeholder="Image URL, or upload a file"
                  value={imageUrl ?? ""}
                  onChange={(e) => setImageUrl(e.target.value)}
                />
                <label className="admin-btn-secondary admin-upload-btn">
                  {uploading ? "Uploading…" : "Upload file"}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    hidden
                    disabled={uploading}
                    onChange={handleFileChange}
                  />
                </label>
                {imageUrl && (
                  <button
                    type="button"
                    className="admin-icon-btn"
                    title="Remove image"
                    onClick={() => setImageUrl("")}
                  >
                    ✕
                  </button>
                )}
              </div>
              {uploadError && <p className="error-text">{uploadError}</p>}
            </div>
          </div>

          <label className="admin-checkbox-field">
            <input
              type="checkbox"
              checked={isAvailable}
              onChange={(e) => setIsAvailable(e.target.checked)}
            />
            <span>Available for ordering</span>
          </label>

          {error && <p className="error-text">{error}</p>}

          <div className="admin-modal-actions">
            <button type="button" className="admin-btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="admin-btn-primary" disabled={saving}>
              {saving ? "Saving…" : isEditing ? "Save changes" : "Create item"}
            </button>
          </div>
        </form>

        {isEditing && item && (
          <CustomizationSection item={item} onChanged={onChanged} />
        )}
      </div>
    </div>
  );
}

function CustomizationSection({
  item,
  onChanged,
}: {
  item: MenuItem;
  onChanged: () => Promise<void>;
}) {
  const [newGroupName, setNewGroupName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-customizations">
      <h3>Customization groups</h3>
      {error && <p className="error-text">{error}</p>}

      {item.customization_groups.length === 0 && (
        <p className="muted-text">No customization groups yet.</p>
      )}

      {item.customization_groups
        .slice()
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((group) => (
          <GroupEditor key={group.id} group={group} busy={busy} run={run} />
        ))}

      <form
        className="admin-add-row"
        onSubmit={(e) => {
          e.preventDefault();
          const name = newGroupName.trim();
          if (!name) return;
          run(() =>
            createGroup(item.id, {
              name,
              is_required: false,
              max_choices: 1,
              sort_order: item.customization_groups.length,
            }),
          ).then(() => setNewGroupName(""));
        }}
      >
        <input
          placeholder="New group name (e.g. Size, Toppings)"
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
        />
        <button type="submit" className="admin-btn-secondary" disabled={busy}>
          + Add group
        </button>
      </form>
    </div>
  );
}

function GroupEditor({
  group,
  busy,
  run,
}: {
  group: CustomizationGroup;
  busy: boolean;
  run: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [name, setName] = useState(group.name);
  const [isRequired, setIsRequired] = useState(group.is_required);
  const [maxChoices, setMaxChoices] = useState(String(group.max_choices));
  const [newOptionName, setNewOptionName] = useState("");
  const [newOptionDelta, setNewOptionDelta] = useState("0");

  useEffect(() => {
    setName(group.name);
    setIsRequired(group.is_required);
    setMaxChoices(String(group.max_choices));
  }, [group.id, group.name, group.is_required, group.max_choices]);

  const dirty =
    name.trim() !== group.name ||
    isRequired !== group.is_required ||
    Number(maxChoices) !== group.max_choices;

  return (
    <div className="admin-group-editor">
      <div className="admin-group-header-row">
        <input
          className="admin-inline-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="admin-checkbox-field admin-checkbox-inline">
          <input
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
          />
          <span>Required</span>
        </label>
        <label className="admin-max-choices">
          <span>Max choices</span>
          <input
            type="number"
            min="1"
            value={maxChoices}
            onChange={(e) => setMaxChoices(e.target.value)}
          />
        </label>
        {dirty && (
          <button
            type="button"
            className="admin-btn-secondary"
            disabled={busy}
            onClick={() =>
              run(() =>
                updateGroup(group.id, {
                  name: name.trim(),
                  is_required: isRequired,
                  max_choices: Math.max(1, Number(maxChoices) || 1),
                }),
              )
            }
          >
            Save
          </button>
        )}
        <button
          type="button"
          className="admin-icon-btn admin-icon-danger"
          title="Delete group"
          disabled={busy}
          onClick={() => {
            if (!confirm(`Delete group "${group.name}" and its options?`)) return;
            run(() => deleteGroup(group.id));
          }}
        >
          ✕
        </button>
      </div>

      <div className="admin-options-list">
        {group.options
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order)
          .map((option) => (
            <div key={option.id} className="admin-option-row">
              <input
                className="admin-inline-input"
                defaultValue={option.name}
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v && v !== option.name) run(() => updateOption(option.id, { name: v }));
                }}
              />
              <input
                className="admin-inline-input admin-price-input"
                type="number"
                step="0.01"
                defaultValue={option.price_delta}
                onBlur={(e) => {
                  const v = Number(e.target.value);
                  if (!Number.isNaN(v) && v !== option.price_delta)
                    run(() => updateOption(option.id, { price_delta: v }));
                }}
              />
              <label className="admin-toggle">
                <input
                  type="checkbox"
                  checked={option.is_available}
                  onChange={(e) =>
                    run(() => updateOption(option.id, { is_available: e.target.checked }))
                  }
                />
              </label>
              <button
                type="button"
                className="admin-icon-btn admin-icon-danger"
                disabled={busy}
                onClick={() => run(() => deleteOption(option.id))}
              >
                ✕
              </button>
            </div>
          ))}

        <form
          className="admin-add-row"
          onSubmit={(e) => {
            e.preventDefault();
            const optName = newOptionName.trim();
            if (!optName) return;
            const delta = Number(newOptionDelta) || 0;
            run(() =>
              createOption(group.id, {
                name: optName,
                price_delta: delta,
                is_available: true,
                sort_order: group.options.length,
              }),
            ).then(() => {
              setNewOptionName("");
              setNewOptionDelta("0");
            });
          }}
        >
          <input
            placeholder="New option name"
            value={newOptionName}
            onChange={(e) => setNewOptionName(e.target.value)}
          />
          <input
            className="admin-price-input"
            type="number"
            step="0.01"
            value={newOptionDelta}
            onChange={(e) => setNewOptionDelta(e.target.value)}
          />
          <button type="submit" className="admin-btn-secondary" disabled={busy}>
            + Add option
          </button>
        </form>
      </div>
    </div>
  );
}
