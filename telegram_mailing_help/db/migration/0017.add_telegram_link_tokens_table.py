from yoyo import step

steps = [
    step(
        """
        CREATE TABLE PWA_TELEGRAM_LINK_TOKENS (
            token    TEXT    PRIMARY KEY,
            users_id INTEGER NOT NULL,
            created  TEXT    NOT NULL,
            used     BOOLEAN DEFAULT 0,
            FOREIGN KEY (users_id) REFERENCES USERS(id) ON DELETE CASCADE
        );
        """,
        "DROP TABLE PWA_TELEGRAM_LINK_TOKENS;"
    ),
]
