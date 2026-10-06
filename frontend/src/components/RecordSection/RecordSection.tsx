import { Fragment, useState } from 'react'
import type { ReactNode } from 'react'
import { RecordForm } from '../RecordForm/RecordForm'
import type { RecordField } from '../RecordForm/RecordForm'
import './RecordSection.css'

type RecordRow<Name extends string> = Record<Name, string> & { id: string }

interface RecordSectionProps<Name extends string> {
  // Leave out where a tab already names the list.
  title?: string
  fields: RecordField<Name>[]
  // Field values for a new record; also fixes which values a form sends.
  emptyValues: Record<Name, string>
  records: RecordRow<Name>[] | undefined
  hasFailed: boolean
  deleteWarning: string
  // Each adds a text input that narrows the list to records whose text
  // contains what was typed. A record must pass every filled-in filter.
  filters?: { placeholder: string; getText: (record: RecordRow<Name>) => string }[]
  // Set to false for a list where a new record would have no parent.
  canAdd?: boolean
  // A read-only first column, for a value that is not one of the fields.
  extraColumn?: { label: string; getValue: (recordId: string) => string }
  onSave: (values: Record<Name, string>, id: string | null) => Promise<unknown>
  onDelete: (id: string) => void
  // Set all four to let the admin open a record's child records: `children`
  // are shown directly under the selected row.
  selectLabel?: string
  selectedId?: string | null
  onSelect?: (id: string | null) => void
  children?: ReactNode
}

// One list of records with create, edit and delete. Shared by the customer,
// shipment and package sections, which supply the fields and the API calls.
export function RecordSection<Name extends string>({
  title,
  fields,
  emptyValues,
  records,
  hasFailed,
  deleteWarning,
  filters = [],
  canAdd = true,
  extraColumn,
  onSave,
  onDelete,
  selectLabel,
  selectedId,
  onSelect,
  children,
}: RecordSectionProps<Name>) {
  // The record being edited, 'new' while creating, null when the form is closed.
  const [editing, setEditing] = useState<RecordRow<Name> | 'new' | null>(null)

  // What was typed into each filter, by its position in `filters`.
  const [filterTexts, setFilterTexts] = useState<string[]>([])

  const visibleRecords = records?.filter((record) =>
    filters.every((filter, index) =>
      filter
        .getText(record)
        .toLowerCase()
        .includes((filterTexts[index] ?? '').trim().toLowerCase()),
    ),
  )

  function setFilterText(index: number, text: string) {
    setFilterTexts((current) => {
      const next = [...current]
      next[index] = text
      return next
    })
  }

  function getFormValues(record: RecordRow<Name> | 'new') {
    if (record === 'new') {
      return emptyValues
    }
    return fields.reduce<Record<Name, string>>(
      (values, field) => ({ ...values, [field.name]: record[field.name] }),
      emptyValues,
    )
  }

  function getDisplayValue(field: RecordField<Name>, record: RecordRow<Name>) {
    const value = record[field.name]
    return field.options?.find((option) => option.value === value)?.label ?? value
  }

  function handleDelete(id: string) {
    if (!window.confirm(deleteWarning)) {
      return
    }
    onDelete(id)
    if (id === selectedId) {
      onSelect?.(null)
    }
  }

  async function handleSave(values: Record<Name, string>) {
    await onSave(values, editing === 'new' || editing === null ? null : editing.id)
    setEditing(null)
  }

  // Shown right where the admin clicked: under the header for a new record,
  // under its row for an edit. In a long list a form at the bottom goes unseen.
  const form = editing && (
    <RecordForm
      key={editing === 'new' ? 'new' : editing.id}
      fields={fields}
      initialValues={getFormValues(editing)}
      onSubmit={handleSave}
      onCancel={() => setEditing(null)}
    />
  )

  const columnCount = fields.length + (extraColumn ? 2 : 1)

  return (
    <section className="record-section">
      <header className="record-section__header">
        {title && <h2 className="record-section__title">{title}</h2>}
        {filters.map((filter, index) => (
          <input
            key={filter.placeholder}
            className="record-section__filter"
            type="search"
            placeholder={filter.placeholder}
            aria-label={filter.placeholder}
            value={filterTexts[index] ?? ''}
            onChange={(event) => setFilterText(index, event.target.value)}
          />
        ))}
        {canAdd && (
          <button type="button" onClick={() => setEditing('new')}>
            Add
          </button>
        )}
      </header>
      {editing === 'new' && form}
      {hasFailed && (
        <p className="record-section__error" role="alert">
          Something went wrong — please try again.
        </p>
      )}
      {visibleRecords?.length === 0 && (
        <p className="record-section__empty">
          {records?.length === 0 ? 'Nothing here yet.' : 'No matches.'}
        </p>
      )}
      {visibleRecords && visibleRecords.length > 0 && (
        <div className="record-section__scroll">
          <table className="record-section__table">
            <thead>
              <tr>
                {extraColumn && <th>{extraColumn.label}</th>}
                {fields.map((field) => (
                  <th key={field.name}>{field.label}</th>
                ))}
                <th />
              </tr>
            </thead>
            <tbody>
              {visibleRecords.map((record) => (
                <Fragment key={record.id}>
                  <tr
                    className={
                      record.id === selectedId ? 'record-section__row--selected' : undefined
                    }
                  >
                    {extraColumn && <td>{extraColumn.getValue(record.id)}</td>}
                    {fields.map((field) => (
                      <td key={field.name}>{getDisplayValue(field, record)}</td>
                    ))}
                    <td className="record-section__actions">
                      {selectLabel && (
                        <button
                          type="button"
                          aria-expanded={record.id === selectedId}
                          onClick={() =>
                            onSelect?.(record.id === selectedId ? null : record.id)
                          }
                        >
                          {selectLabel}
                        </button>
                      )}
                      <button type="button" onClick={() => setEditing(record)}>
                        Edit
                      </button>
                      <button type="button" onClick={() => handleDelete(record.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                  {editing !== 'new' && editing?.id === record.id && (
                    <tr>
                      <td colSpan={columnCount}>{form}</td>
                    </tr>
                  )}
                  {record.id === selectedId && children && (
                    <tr>
                      <td className="record-section__children" colSpan={columnCount}>
                        {children}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
