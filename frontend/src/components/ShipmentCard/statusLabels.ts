import type { ShipmentStatus } from "../../api/generated/chat";

export const STATUS_LABELS: Record<ShipmentStatus, string> = {
  label_created: "Label created",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  exception: "Exception",
};
