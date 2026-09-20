import random
import uuid
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.customer import Customer
from app.models.package import Package
from app.models.shipment import Shipment, ShipmentStatus

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph",
    "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy", "Matthew",
    "Lisa", "Anthony", "Betty", "Mark", "Margaret", "Paul", "Sandra",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
]
STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St", "Pine St",
    "Washington Ave", "Lake View Rd", "Sunset Blvd", "Highland Ave", "River Rd",
    "Park Ave", "Church St", "Willow Way", "Birch St",
]
CITIES = [
    ("Austin", "TX"), ("Denver", "CO"), ("Seattle", "WA"), ("Portland", "OR"),
    ("Chicago", "IL"), ("Boston", "MA"), ("Miami", "FL"), ("Phoenix", "AZ"),
    ("Atlanta", "GA"), ("Dallas", "TX"), ("Berlin", "DE"), ("Amsterdam", "NL"),
    ("Lisbon", "PT"), ("Dublin", "IE"), ("Vienna", "AT"),
]
PACKAGE_ITEMS = [
    "Wireless Headphones", "Running Shoes", "Laptop Charger", "Coffee Maker",
    "Yoga Mat", "Desk Lamp", "Bluetooth Speaker", "Backpack", "Water Bottle",
    "Phone Case", "Board Game", "Kitchen Knife Set", "Winter Jacket",
    "Sunglasses", "Electric Kettle",
]

NUM_CUSTOMERS = 30
STATUS_WEIGHTS = {
    ShipmentStatus.IN_TRANSIT: 35,
    ShipmentStatus.DELIVERED: 35,
    ShipmentStatus.OUT_FOR_DELIVERY: 15,
    ShipmentStatus.LABEL_CREATED: 10,
    ShipmentStatus.EXCEPTION: 5,
}


def mock_phone_number() -> str:
    return f"+1{random.randint(2_000_000_000, 9_999_999_999)}"


def mock_tracking_number() -> str:
    return f"ME{random.randint(100_000_000, 999_999_999)}"


def mock_address() -> str:
    city, state = random.choice(CITIES)
    return (
        f"{random.randint(100, 9999)} {random.choice(STREET_NAMES)}, "
        f"{city}, {state} {random.randint(10000, 99999)}"
    )


def random_status() -> ShipmentStatus:
    statuses, weights = zip(*STATUS_WEIGHTS.items())
    return random.choices(statuses, weights=weights, k=1)[0]


def seed() -> None:
    db = SessionLocal()
    try:
        db.query(Package).delete()
        db.query(Shipment).delete()
        db.query(Customer).delete()

        customers = [
            Customer(
                id=uuid.uuid4(),
                first_name=random.choice(FIRST_NAMES),
                last_name=random.choice(LAST_NAMES),
                phone_number=mock_phone_number(),
                address=mock_address(),
            )
            for _ in range(NUM_CUSTOMERS)
        ]
        db.add_all(customers)
        db.flush()

        shipment_count = 0
        for customer in customers:
            for _ in range(random.randint(1, 3)):
                origin = random.choice(CITIES)[0]
                destination = random.choice([c[0] for c in CITIES if c[0] != origin])
                shipment = Shipment(
                    id=uuid.uuid4(),
                    customer_id=customer.id,
                    tracking_number=mock_tracking_number(),
                    status=random_status(),
                    carrier="MockExpress",
                    origin=origin,
                    destination=destination,
                    estimated_delivery=(
                        datetime.now(timezone.utc)
                        + timedelta(days=random.randint(-5, 10))
                    ).date(),
                    last_update=datetime.now(timezone.utc)
                    - timedelta(hours=random.randint(0, 72)),
                )
                db.add(shipment)
                db.flush()
                shipment_count += 1

                for _ in range(random.randint(1, 2)):
                    db.add(
                        Package(
                            id=uuid.uuid4(),
                            shipment_id=shipment.id,
                            description=random.choice(PACKAGE_ITEMS),
                            weight_kg=round(random.uniform(0.2, 25.0), 2),
                            declared_value=round(random.uniform(10, 500), 2),
                        )
                    )

        db.commit()
        print(f"Seeded {len(customers)} customers and {shipment_count} shipments.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
