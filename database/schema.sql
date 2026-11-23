-- Schema relationnel normalise (3FN) pour les donnees structurees.
-- SQL volontairement portable : PostgreSQL (cluster) et SQLite (tests locaux).

-- referentiel des types d'operation (evite de repeter le texte dans 100 000 lignes)
CREATE TABLE IF NOT EXISTS transaction_types (
    type_id     INTEGER PRIMARY KEY,
    type_code   VARCHAR(20) NOT NULL UNIQUE
);

-- un compte = une ligne ; le type (client/marchand) est une propriete du compte
CREATE TABLE IF NOT EXISTS accounts (
    account_id    VARCHAR(20) PRIMARY KEY,
    account_kind  VARCHAR(10) NOT NULL CHECK (account_kind IN ('CLIENT', 'MARCHAND'))
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id   BIGINT PRIMARY KEY,
    sender_id        VARCHAR(20) NOT NULL REFERENCES accounts(account_id),
    receiver_id      VARCHAR(20) NOT NULL REFERENCES accounts(account_id),
    type_id          INTEGER NOT NULL REFERENCES transaction_types(type_id),
    amount           DOUBLE PRECISION NOT NULL CHECK (amount >= 0),
    oldbalance_org   DOUBLE PRECISION,
    newbalance_org   DOUBLE PRECISION,
    oldbalance_dest  DOUBLE PRECISION,
    newbalance_dest  DOUBLE PRECISION,
    is_fraud         INTEGER NOT NULL DEFAULT 0 CHECK (is_fraud IN (0, 1)),
    tx_time          TIMESTAMP NOT NULL
);

-- alertes produites par le modele (partie 3), une par transaction signalee
CREATE TABLE IF NOT EXISTS fraud_alerts (
    alert_id        INTEGER PRIMARY KEY,
    transaction_id  BIGINT NOT NULL UNIQUE REFERENCES transactions(transaction_id),
    risk_reasons    TEXT,
    status          VARCHAR(12) NOT NULL DEFAULT 'A_VERIFIER'
                    CHECK (status IN ('A_VERIFIER', 'CONFIRMEE', 'REJETEE'))
);

-- index pour les requetes de l'API et de l'analyse
CREATE INDEX IF NOT EXISTS idx_tx_sender   ON transactions(sender_id);
CREATE INDEX IF NOT EXISTS idx_tx_receiver ON transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_tx_fraud    ON transactions(is_fraud);
