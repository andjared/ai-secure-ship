import "./ShipmentCard.css";
import type { ShipmentInfo, ShipmentStatus } from "../../api/generated/chat";

interface ShipmentCardProps {
  shipment: ShipmentInfo;
}

const STATUS_LABELS: Record<ShipmentStatus, string> = {
  label_created: "Label created",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  exception: "Exception",
};

// A plain date ("2026-10-03") parses as UTC midnight, so format it in UTC
// to avoid showing the day before in timezones behind UTC.
function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  });
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function ShipmentCard({ shipment }: ShipmentCardProps) {
  return (
    <article className="shipment-card">
      <header className="shipment-card__header">
        <span className="shipment-card__tracking">
          {shipment.tracking_number}
        </span>
        <span
          className={`shipment-card__status shipment-card__status--${shipment.status}`}
        >
          {STATUS_LABELS[shipment.status]}
        </span>
      </header>
      <div className="shipment-card__route">
        {shipment.origin} → {shipment.destination}
      </div>
      <dl className="shipment-card__details">
        <dt>Carrier</dt>
        <dd>{shipment.carrier}</dd>
        <dt>Estimated delivery</dt>
        <dd>{formatDate(shipment.estimated_delivery)}</dd>
        <dt>Last update</dt>
        <dd>{formatDateTime(shipment.last_update)}</dd>
      </dl>
      <ul className="shipment-card__packages">
        {shipment.packages.map((packageInfo, index) => (
          <li key={index} className="shipment-card__package">
            <span>{packageInfo.description}</span>
            <span className="shipment-card__package-meta">
              {packageInfo.weight_kg} kg · value {packageInfo.declared_value}
            </span>
          </li>
        ))}
      </ul>
    </article>
  );
}
