from yoyo import step

steps = [
    step("ALTER TABLE USERS ADD COLUMN email TEXT DEFAULT NULL;"),
    step("ALTER TABLE USERS ADD COLUMN password_hash TEXT DEFAULT NULL;"),
    step("ALTER TABLE USERS ADD COLUMN pwa_last_login TEXT DEFAULT NULL;"),
    step(
        "CREATE UNIQUE INDEX users_email_unique ON USERS (email) WHERE email IS NOT NULL;",
        "DROP INDEX users_email_unique;"
    ),
]
