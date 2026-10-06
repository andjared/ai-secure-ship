import { useState } from 'react'
import type { FormEvent } from 'react'
import './RecordForm.css'

export interface RecordField<Name extends string> {
  name: Name
  label: string
  type?: 'text' | 'date' | 'number'
  options?: { value: string; label: string }[]
}

interface RecordFormProps<Name extends string> {
  fields: RecordField<Name>[]
  initialValues: Record<Name, string>
  onSubmit: (values: Record<Name, string>) => Promise<unknown>
  onCancel: () => void
}

export function RecordForm<Name extends string>({
  fields,
  initialValues,
  onSubmit,
  onCancel,
}: RecordFormProps<Name>) {
  const [values, setValues] = useState(initialValues)
  const [isSaving, setIsSaving] = useState(false)
  const [hasFailed, setHasFailed] = useState(false)

  function setValue(name: Name, value: string) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setIsSaving(true)
    setHasFailed(false)
    try {
      await onSubmit(values)
    } catch {
      setHasFailed(true)
      setIsSaving(false)
    }
  }

  return (
    <form className="record-form" onSubmit={handleSubmit}>
      {fields.map((field) => (
        <label key={field.name} className="record-form__field">
          {field.label}
          {field.options ? (
            <select
              value={values[field.name]}
              onChange={(event) => setValue(field.name, event.target.value)}
            >
              {field.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={field.type ?? 'text'}
              value={values[field.name]}
              onChange={(event) => setValue(field.name, event.target.value)}
              required
              maxLength={200}
              min={field.type === 'number' ? 0.01 : undefined}
              step={field.type === 'number' ? 0.01 : undefined}
            />
          )}
        </label>
      ))}
      {hasFailed && (
        <p className="record-form__error" role="alert">
          Could not save — please check the values and try again.
        </p>
      )}
      <div className="record-form__actions">
        <button className="record-form__save" type="submit" disabled={isSaving}>
          Save
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}
