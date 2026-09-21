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
SERBIAN_FIRST_NAMES = [
    "Marko", "Nikola", "Stefan", "Milan", "Nemanja", "Luka", "Đorđe",
    "Aleksandar", "Lazar", "Vladimir", "Jelena", "Milica", "Ana", "Marija",
    "Jovana", "Ivana", "Teodora", "Katarina", "Dragana", "Tijana",
]
SERBIAN_LAST_NAMES = [
    "Petrović", "Jovanović", "Nikolić", "Đorđević", "Ilić", "Stanković",
    "Pavlović", "Milošević", "Marković", "Popović", "Stojanović", "Simić",
    "Todorović", "Kovačević", "Lazić", "Ćirić", "Vasić", "Mitrović",
    "Radović", "Đurđević",
]
SERBIAN_STREET_NAMES = [
    "Knez Mihailova", "Bulevar kralja Aleksandra", "Nemanjina", "Cara Dušana",
    "Vojvode Stepe", "Kralja Milana", "Svetog Save", "Jovana Cvijića",
    "Cara Lazara", "Njegoševa",
]
# (city, postal code)
SERBIAN_CITIES = [
    ("Beograd", "11000"), ("Novi Sad", "21000"), ("Niš", "18000"),
    ("Kragujevac", "34000"), ("Subotica", "24000"), ("Čačak", "32000"),
    ("Kraljevo", "36000"), ("Šabac", "15000"), ("Zrenjanin", "23000"),
    ("Pančevo", "26000"),
]
SERBIAN_MOBILE_PREFIXES = [60, 61, 62, 63, 64, 65, 66, 69]
ROUTE_CITIES = [city for city, _ in CITIES] + [city for city, _ in SERBIAN_CITIES]
PACKAGE_ITEMS = [
    "Wireless Headphones", "Running Shoes", "Laptop Charger", "Coffee Maker",
    "Yoga Mat", "Desk Lamp", "Bluetooth Speaker", "Backpack", "Water Bottle",
    "Phone Case", "Board Game", "Kitchen Knife Set", "Winter Jacket",
    "Sunglasses", "Electric Kettle",
]

NUM_CUSTOMERS = 30
NUM_SERBIAN_CUSTOMERS = 10
STATUS_WEIGHTS = {
    ShipmentStatus.IN_TRANSIT: 35,
    ShipmentStatus.DELIVERED: 35,
    ShipmentStatus.OUT_FOR_DELIVERY: 15,
    ShipmentStatus.LABEL_CREATED: 10,
    ShipmentStatus.EXCEPTION: 5,
}


def mock_phone_number() -> str:
    return f"+1{random.randint(2_000_000_000, 9_999_999_999)}"


def mock_serbian_phone_number() -> str:
    prefix = random.choice(SERBIAN_MOBILE_PREFIXES)
    return f"+381{prefix}{random.randint(1_000_000, 9_999_999)}"


def mock_serbian_address() -> str:
    city, postal_code = random.choice(SERBIAN_CITIES)
    return (
        f"{random.choice(SERBIAN_STREET_NAMES)} {random.randint(1, 150)}, "
        f"{postal_code} {city}"
    )


def mock_us_customer() -> Customer:
    return Customer(
        id=uuid.uuid4(),
        first_name=random.choice(FIRST_NAMES),
        last_name=random.choice(LAST_NAMES),
        phone_number=mock_phone_number(),
        address=mock_address(),
    )


def mock_serbian_customer() -> Customer:
    return Customer(
        id=uuid.uuid4(),
        first_name=random.choice(SERBIAN_FIRST_NAMES),
        last_name=random.choice(SERBIAN_LAST_NAMES),
        phone_number=mock_serbian_phone_number(),
        address=mock_serbian_address(),
    )


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
            mock_us_customer()
            for _ in range(NUM_CUSTOMERS - NUM_SERBIAN_CUSTOMERS)
        ] + [mock_serbian_customer() for _ in range(NUM_SERBIAN_CUSTOMERS)]
        db.add_all(customers)
        db.flush()

        shipment_count = 0
        for customer in customers:
            for _ in range(random.randint(1, 3)):
                origin = random.choice(ROUTE_CITIES)
                destination = random.choice([c for c in ROUTE_CITIES if c != origin])
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
