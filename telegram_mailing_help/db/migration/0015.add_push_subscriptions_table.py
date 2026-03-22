from yoyo import step

steps = [
    step(
        """
        CREATE TABLE PWA_PUSH_SUBSCRIPTIONS (
            id       INTEGER PRIMARY KEY,
            users_id INTEGER NOT NULL,
            endpoint TEXT    NOT NULL,
            p256dh   TEXT    NOT NULL,
            auth     TEXT    NOT NULL,
            created  TEXT    NOT NULL,
            FOREIGN KEY (users_id) REFERENCES USERS(id) ON DELETE CASCADE
        );
        """,
        "DROP TABLE PWA_PUSH_SUBSCRIPTIONS;"
    ),
    step(
        "CREATE UNIQUE INDEX push_sub_endpoint_idx ON PWA_PUSH_SUBSCRIPTIONS (endpoint);",
        "DROP INDEX push_sub_endpoint_idx;"
    ),
    step(
        "CREATE INDEX push_sub_users_idx ON PWA_PUSH_SUBSCRIPTIONS (users_id);",
        "DROP INDEX push_sub_users_idx;"
    ),
]
