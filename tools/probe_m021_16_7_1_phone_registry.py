from app.osint.manager import OsintManager
from app.osint.models import OsintTargetType

manager = OsintManager()

for connector in manager.registry.supported(
    OsintTargetType.PHONE
):
    print(
        connector.name,
        "|",
        connector.__class__.__name__,
        "| available=",
        connector.is_available(),
    )
