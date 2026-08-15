import { useEffect, useState } from "react";
import type { MenuCategory, MenuItem } from "../types";
import {
  createCategory,
  deleteCategory,
  deleteItem,
  fetchAdminCategories,
  updateCategory,
  updateItem,
} from "./api";
import { UnauthorizedError } from "./auth";
import { ItemModal } from "./ItemModal";

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

type ItemModalState = { categoryId: string; item: MenuItem | null };

interface MenuManagerProps {
  onUnauthorized: () => void;
}

export function MenuManager({ onUnauthorized }: MenuManagerProps) {
  const [categories, setCategories] = useState<MenuCategory[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [renamingCategoryId, setRenamingCategoryId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [itemModal, setItemModal] = useState<ItemModalState | null>(null);

  async function reload(): Promise<MenuCategory[]> {
    const cats = await fetchAdminCategories();
    setCategories(cats);
    return cats;
  }

  useEffect(() => {
    reload()
      .then((cats) => {
        setSelectedCategoryId((prev) => prev ?? cats[0]?.id ?? null);
      })
      .catch((err) => {
        if (err instanceof UnauthorizedError) {
          onUnauthorized();
          return;
        }
        setLoadError(errorMessage(err));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAction(fn: () => Promise<unknown>) {
    setActionError(null);
    try {
      await fn();
      await reload();
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        onUnauthorized();
        return;
      }
      setActionError(errorMessage(err));
    }
  }

  function moveSortOrder<T extends { id: string; sort_order: number }>(
    list: T[],
    id: string,
    direction: -1 | 1,
    persist: (a: T, b: T) => Promise<unknown>,
  ) {
    const sorted = [...list].sort((a, b) => a.sort_order - b.sort_order);
    const idx = sorted.findIndex((x) => x.id === id);
    const swapIdx = idx + direction;
    if (idx === -1 || swapIdx < 0 || swapIdx >= sorted.length) return;
    const a = sorted[idx];
    const b = sorted[swapIdx];
    runAction(() => persist(a, b));
  }

  if (loadError) {
    return <p className="error-text">Couldn't load the menu: {loadError}</p>;
  }

  if (!categories) {
    return <p className="muted-text">Loading…</p>;
  }

  const selectedCategory = categories.find((c) => c.id === selectedCategoryId) ?? null;
  const liveItem =
    itemModal?.item != null
      ? (categories.flatMap((c) => c.items).find((i) => i.id === itemModal.item!.id) ??
        itemModal.item)
      : null;

  return (
    <>
      {actionError && <p className="error-text admin-action-error">{actionError}</p>}

      <div className="admin-layout">
        <aside className="admin-sidebar panel">
          <h2>Categories</h2>
          <ul className="admin-category-list">
            {categories
              .slice()
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((cat) => (
                <li key={cat.id}>
                  <div
                    className={`admin-category-row${cat.id === selectedCategoryId ? " active" : ""}`}
                  >
                    <button
                      type="button"
                      className="admin-category-select"
                      onClick={() => setSelectedCategoryId(cat.id)}
                    >
                      {renamingCategoryId === cat.id ? (
                        <input
                          autoFocus
                          className="admin-inline-input"
                          value={renameValue}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => {
                            const name = renameValue.trim();
                            setRenamingCategoryId(null);
                            if (name && name !== cat.name) {
                              runAction(() => updateCategory(cat.id, { name }));
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                            if (e.key === "Escape") setRenamingCategoryId(null);
                          }}
                        />
                      ) : (
                        <>
                          <span className={cat.is_available ? undefined : "muted-text"}>
                            {cat.name}
                          </span>
                          <span className="muted-text admin-count">{cat.items.length}</span>
                        </>
                      )}
                    </button>
                    <div className="admin-row-actions">
                      <label
                        className="admin-toggle"
                        title={cat.is_available ? "Category is visible on the menu" : "Category is hidden from the menu"}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={cat.is_available}
                          onChange={(e) =>
                            runAction(() =>
                              updateCategory(cat.id, { is_available: e.target.checked }),
                            )
                          }
                        />
                      </label>
                      <button
                        type="button"
                        className="admin-icon-btn"
                        title="Move up"
                        onClick={() =>
                          moveSortOrder(categories, cat.id, -1, (a, b) =>
                            Promise.all([
                              updateCategory(a.id, { sort_order: b.sort_order }),
                              updateCategory(b.id, { sort_order: a.sort_order }),
                            ]),
                          )
                        }
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        className="admin-icon-btn"
                        title="Move down"
                        onClick={() =>
                          moveSortOrder(categories, cat.id, 1, (a, b) =>
                            Promise.all([
                              updateCategory(a.id, { sort_order: b.sort_order }),
                              updateCategory(b.id, { sort_order: a.sort_order }),
                            ]),
                          )
                        }
                      >
                        ▼
                      </button>
                      <button
                        type="button"
                        className="admin-icon-btn"
                        title="Rename"
                        onClick={() => {
                          setRenamingCategoryId(cat.id);
                          setRenameValue(cat.name);
                        }}
                      >
                        ✎
                      </button>
                      <button
                        type="button"
                        className="admin-icon-btn admin-icon-danger"
                        title="Delete category"
                        onClick={() => {
                          if (
                            !confirm(
                              `Delete category "${cat.name}"? This also deletes its ${cat.items.length} item(s).`,
                            )
                          )
                            return;
                          runAction(() => deleteCategory(cat.id)).then(() => {
                            setSelectedCategoryId((prev) => (prev === cat.id ? null : prev));
                          });
                        }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </li>
              ))}
          </ul>

          <form
            className="admin-new-category-form"
            onSubmit={(e) => {
              e.preventDefault();
              const name = newCategoryName.trim();
              if (!name) return;
              const maxSort = categories.reduce((m, c) => Math.max(m, c.sort_order), -1);
              runAction(() =>
                createCategory({ name, sort_order: maxSort + 1, is_available: true }),
              ).then(() => setNewCategoryName(""));
            }}
          >
            <input
              className="admin-inline-input"
              placeholder="New category name"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
            />
            <button type="submit" className="admin-btn-secondary">
              + Add
            </button>
          </form>
        </aside>

        <section className="admin-main panel">
          {!selectedCategory ? (
            <p className="muted-text">Select or create a category to manage its items.</p>
          ) : (
            <>
              <div className="admin-main-header">
                <h2>{selectedCategory.name}</h2>
                <button
                  type="button"
                  className="admin-btn-primary"
                  onClick={() => setItemModal({ categoryId: selectedCategory.id, item: null })}
                >
                  + Add item
                </button>
              </div>

              {selectedCategory.items.length === 0 ? (
                <p className="muted-text">No items in this category yet.</p>
              ) : (
                <table className="admin-items-table">
                  <thead>
                    <tr>
                      <th />
                      <th>Name</th>
                      <th>Price</th>
                      <th>Available</th>
                      <th>Customizations</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCategory.items
                      .slice()
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((item) => (
                        <tr key={item.id}>
                          <td className="admin-reorder-cell">
                            <button
                              type="button"
                              className="admin-icon-btn"
                              title="Move up"
                              onClick={() =>
                                moveSortOrder(selectedCategory.items, item.id, -1, (a, b) =>
                                  Promise.all([
                                    updateItem(a.id, { sort_order: b.sort_order }),
                                    updateItem(b.id, { sort_order: a.sort_order }),
                                  ]),
                                )
                              }
                            >
                              ▲
                            </button>
                            <button
                              type="button"
                              className="admin-icon-btn"
                              title="Move down"
                              onClick={() =>
                                moveSortOrder(selectedCategory.items, item.id, 1, (a, b) =>
                                  Promise.all([
                                    updateItem(a.id, { sort_order: b.sort_order }),
                                    updateItem(b.id, { sort_order: a.sort_order }),
                                  ]),
                                )
                              }
                            >
                              ▼
                            </button>
                          </td>
                          <td>
                            <div className="admin-item-name-cell">
                              {item.image_url && <img src={item.image_url} alt="" />}
                              <div>
                                <div className="item-name">{item.name}</div>
                                {item.description && (
                                  <div className="muted-text admin-item-desc">{item.description}</div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td>₹{item.price.toFixed(2)}</td>
                          <td>
                            <label className="admin-toggle">
                              <input
                                type="checkbox"
                                checked={item.is_available}
                                onChange={(e) =>
                                  runAction(() =>
                                    updateItem(item.id, { is_available: e.target.checked }),
                                  )
                                }
                              />
                            </label>
                          </td>
                          <td className="muted-text">
                            {item.customization_groups.length > 0
                              ? `${item.customization_groups.length} group(s)`
                              : "—"}
                          </td>
                          <td className="admin-row-actions">
                            <button
                              type="button"
                              className="admin-btn-secondary"
                              onClick={() =>
                                setItemModal({ categoryId: selectedCategory.id, item })
                              }
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="admin-icon-btn admin-icon-danger"
                              title="Delete item"
                              onClick={() => {
                                if (!confirm(`Delete item "${item.name}"?`)) return;
                                runAction(() => deleteItem(item.id));
                              }}
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>
      </div>

      {itemModal && (
        <ItemModal
          categories={categories}
          categoryId={itemModal.categoryId}
          item={itemModal.item ? (liveItem ?? itemModal.item) : null}
          onClose={() => setItemModal(null)}
          onChanged={async () => {
            await reload();
          }}
          onCreated={(created) => setItemModal({ categoryId: itemModal.categoryId, item: created })}
        />
      )}
    </>
  );
}
