-- =============================================================================
-- SCHÉMA DE BASE DE DONNÉES - CONTEXTE TÉLÉCOM / SAAS
-- Projet : Prédiction de Churn & Segmentation Client
-- Usage : Modélisation des données clients pour la prédiction du désabonnement
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Table : clients
-- Description : Profil démographique et d'acquisition de chaque client
-- Impact Business : Segmenter par canal et région pour le ciblage marketing
-- -----------------------------------------------------------------------------
CREATE TABLE clients (
    client_id           VARCHAR(20) PRIMARY KEY,
    date_inscription    DATE NOT NULL,
    genre               VARCHAR(10),
    senior_citizen      SMALLINT DEFAULT 0,  -- 0 = Non, 1 = Oui (65+)
    partenaire          VARCHAR(3),          -- Oui / Non
    personnes_a_charge  VARCHAR(3),          -- Oui / Non
    canal_acquisition   VARCHAR(30),         -- Web, Partenariat, Télévente, Magasin
    region              VARCHAR(50),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Table : produits
-- Description : Catalogue des offres (internet, mobile, bundle)
-- Impact Business : Prix et type d'offre influencent fortement le churn
-- -----------------------------------------------------------------------------
CREATE TABLE produits (
    produit_id      VARCHAR(10) PRIMARY KEY,
    nom             VARCHAR(100),
    categorie       VARCHAR(20),  -- Internet, Mobile, Bundle
    tarif_base      DECIMAL(10, 2)
);

-- -----------------------------------------------------------------------------
-- Table : abonnements
-- Description : Lien client <-> produit avec dates et statut
-- Impact Business : La durée d'engagement (tenure) et le type de contrat sont des signaux clés
-- -----------------------------------------------------------------------------
CREATE TABLE abonnements (
    abonnement_id   SERIAL PRIMARY KEY,
    client_id       VARCHAR(20) REFERENCES clients(client_id),
    produit_id      VARCHAR(10) REFERENCES produits(produit_id),
    date_debut      DATE NOT NULL,
    date_fin        DATE,                    -- NULL si actif, renseigné si résilié
    tarif_mensuel   DECIMAL(10, 2),
    type_contrat    VARCHAR(20),            -- Mensuel, 1_an, 2_ans
    facturation_sans_papier VARCHAR(3),     -- Oui / Non
    mode_paiement   VARCHAR(40),             -- CB, Virement, Prélèvement, Chèque
    statut          VARCHAR(20) DEFAULT 'actif',  -- actif, résilié
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Table : facturation
-- Description : Historique des factures pour calcul revenus et retard de paiement
-- Impact Business : Retards de paiement = signal de risque de churn
-- -----------------------------------------------------------------------------
CREATE TABLE facturation (
    facture_id      SERIAL PRIMARY KEY,
    client_id       VARCHAR(20) REFERENCES clients(client_id),
    date_facture    DATE NOT NULL,
    montant         DECIMAL(10, 2),
    paye_a_temps    SMALLINT,   -- 0 = retard, 1 = à temps
    date_paiement   DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Table : interactions_support
-- Description : Appels et tickets support (signal de mécontentement)
-- Impact Business : Nombre et type d'interactions corrélés au churn
-- -----------------------------------------------------------------------------
CREATE TABLE interactions_support (
    interaction_id  SERIAL PRIMARY KEY,
    client_id       VARCHAR(20) REFERENCES clients(client_id),
    date_interaction DATE NOT NULL,
    type_interaction VARCHAR(20),   -- appel, ticket, chat
    theme           VARCHAR(50),   -- technique, facturation, résiliation
    resolution_satisfaisante SMALLINT,  -- 0 = Non, 1 = Oui
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Table : usage_mensuel
-- Description : Métriques d'utilisation (connexions, volume, appels)
-- Impact Business : Baisse d'usage = signal précoce de désengagement
-- -----------------------------------------------------------------------------
CREATE TABLE usage_mensuel (
    usage_id        SERIAL PRIMARY KEY,
    client_id       VARCHAR(20) REFERENCES clients(client_id),
    mois            DATE NOT NULL,          -- Premier jour du mois
    nb_connexions   INTEGER DEFAULT 0,
    volume_data_go  DECIMAL(10, 2) DEFAULT 0,
    duree_appels_min INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Index pour accélérer les jointures et filtres sur les requêtes analytiques
-- -----------------------------------------------------------------------------
CREATE INDEX idx_abonnements_client ON abonnements(client_id);
CREATE INDEX idx_abonnements_statut ON abonnements(statut);
CREATE INDEX idx_facturation_client ON facturation(client_id);
CREATE INDEX idx_interactions_client ON interactions_support(client_id);
CREATE INDEX idx_usage_client_mois ON usage_mensuel(client_id, mois);
