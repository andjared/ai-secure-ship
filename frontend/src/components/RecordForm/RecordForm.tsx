import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import './RecordForm.css'

export interface RecordField<Name extends string> {
  name: Name
  label: string
  type?: 'text' | 'date' | 'number'
  options?: { value: string; label: string }[]
  // Fewest characters a text value may have (1 when left out).
  minLength?: number
  // Count only the digits towards minLength, e.g. for a phone number.
  countsDigitsOnly?: boolean
  // Largest value a number field may hold.
  max?: number
}

const MAX_TEXT_LENGTH = 200

// The message to show under a field, or null when its value is fine.
function getFieldError<Name extends string>(
  field: RecordField<Name>,
  rawValue: string,
) {
  if (field.options) {
    return rawValue ? null : `${field.label} is required.`
  }
  const value = rawValue.trim()
  if (!value) {
    return `${field.label} is required.`
  }
  if (field.type === 'number') {
    if (!/^\d*\.?\d+$/.test(value) || Number(value) <= 0) {
      return `${field.label} must be a number greater than 0.`
    }
    if (!/^\d*(\.\d{1,2})?$/.test(value)) {
      return `${field.label} can have at most 2 decimal places.`
    }
    if (field.max !== undefined && Number(value) > field.max) {
      return `${field.label} must be at most ${field.max}.`
    }
    return null
  }
  if (field.type === 'date') {
    return Number.isNaN(Date.parse(value)) ? `${field.label} is required.` : null
  }
  const length = field.countsDigitsOnly
    ? value.replace(/\D/g, '').length
    : value.length
  if (field.minLength !== undefined && length < field.minLength) {
    const unit = field.countsDigitsOnly ? 'digits' : 'characters'
    return `${field.label} must be at least ${field.minLength} ${unit}.`
  }
  if (value.length > MAX_TEXT_LENGTH) {
    return `${field.label} must be at most ${MAX_TEXT_LENGTH} characters.`
  }
  return null
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
  // A field's error is shown once the admin has left it or pressed Save.
  const [touchedNames, setTouchedNames] = useState<Name[]>([])
  const [hasTriedToSave, setHasTriedToSave] = useState(false)
  const formId = useId()

  function setValue(name: Name, value: string) {
    setValues((current) => ({ ...current, [name]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setHasTriedToSave(true)
    const firstInvalid = fields.find((field) =>
      getFieldError(field, values[field.name]),
    )
    if (firstInvalid) {
      const input = event.currentTarget.elements.namedItem(firstInvalid.name)
      if (input instanceof HTMLElement) {
        input.focus()
      }
      return
    }
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
    <form className="record-form" onSubmit={handleSubmit} noValidate>
      {fields.map((field) => {
        const isShowingError =
          hasTriedToSave || touchedNames.includes(field.name)
        const error = isShowingError
          ? getFieldError(field, values[field.name])
          : null
        const errorId = `${formId}-${field.name}-error`
        return (
          <label key={field.name} className="record-form__field">
            {field.label}
            {field.options ? (
              <select
                name={field.name}
                value={values[field.name]}
                onChange={(event) => setValue(field.name, event.target.value)}
              >
                {!values[field.name] && (
                  <option value="" disabled>
                    Choose…
                  </option>
                )}
                {field.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                name={field.name}
                type={field.type ?? 'text'}
                value={values[field.name]}
                onChange={(event) => setValue(field.name, event.target.value)}
                onBlur={() =>
                  setTouchedNames((current) => [...current, field.name])
                }
                maxLength={MAX_TEXT_LENGTH}
                step={field.type === 'number' ? 0.01 : undefined}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? errorId : undefined}
              />
            )}
            {error && (
              <span id={errorId} className="record-form__field-error">
                {error}
              </span>
            )}
          </label>
        )
      })}
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
