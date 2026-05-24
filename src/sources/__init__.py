from .naukri import fetch as fetch_naukri
from .linkedin import fetch as fetch_linkedin
from .indeed import fetch as fetch_indeed
from .foundit import fetch as fetch_foundit
from .instahyre import fetch as fetch_instahyre
from .hirist import fetch as fetch_hirist

__all__ = [
    "fetch_naukri",
    "fetch_linkedin",
    "fetch_indeed",
    "fetch_foundit",
    "fetch_instahyre",
    "fetch_hirist",
]
