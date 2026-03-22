from dataclasses import dataclass


@dataclass
class PwaConfiguration:
    enabled: bool = False
    port: int = 23446
    host: str = "localhost"
    vapid_subject: str = "mailto:admin@example.com"
