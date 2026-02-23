-- =============================================================================
-- REQUÊTE SQL D'EXTRACTION DE LA TABLE DE FEATURES POUR LE MODÈLE DE CHURN
-- Projet : Prédiction de Churn & Segmentation Client
-- Objectif : Une ligne par client avec agrégats et signaux comportementaux
-- =============================================================================
-- Contraintes : 
--   - Période d'analyse : 12 derniers mois (à adapter via variables)
--   - Cible (churn) : client avec abonnement résilié dans la fenêtre cible
-- =============================================================================

WITH 
-- Fenêtre de référence : on fixe une date "aujourd'hui" pour l'entraînement
params AS (
    SELECT 
        DATE '2024-12-31' AS date_reference,
        DATE '2024-01-01' AS debut_periode
),

-- Dernier abonnement actif ou dernière résiliation par client (avant date_ref)
dernier_abonnement AS (
    SELECT 
        a.client_id,
        a.produit_id,
        a.date_debut,
        a.date_fin,
        a.tarif_mensuel,
        a.type_contrat,
        a.statut,
        p.categorie AS categorie_produit,
        ROW_NUMBER() OVER (PARTITION BY a.client_id ORDER BY a.date_debut DESC) AS rn
    FROM abonnements a
    JOIN produits p ON a.produit_id = p.produit_id
    CROSS JOIN params pr
    WHERE a.date_debut <= pr.date_reference
),

-- Agrégats facturation : CA total, retard de paiement
agg_facturation AS (
    SELECT 
        f.client_id,
        COUNT(*) AS nb_factures,
        SUM(f.montant) AS total_charges,
        AVG(f.montant) AS montant_moyen_facture,
        SUM(CASE WHEN f.paye_a_temps = 0 THEN 1 ELSE 0 END) AS nb_retards_paiement,
        SUM(CASE WHEN f.paye_a_temps = 1 THEN 1 ELSE 0 END) AS nb_paiements_a_temps
    FROM facturation f
    CROSS JOIN params pr
    WHERE f.date_facture BETWEEN pr.debut_periode AND pr.date_reference
    GROUP BY f.client_id
),

-- Agrégats support : nombre d'interactions et taux de résolution
agg_support AS (
    SELECT 
        i.client_id,
        COUNT(*) AS nb_interactions_support,
        SUM(CASE WHEN i.theme = 'résiliation' THEN 1 ELSE 0 END) AS nb_contacts_resiliation,
        AVG(i.resolution_satisfaisante) AS taux_resolution_satisfaisante
    FROM interactions_support i
    CROSS JOIN params pr
    WHERE i.date_interaction BETWEEN pr.debut_periode AND pr.date_reference
    GROUP BY i.client_id
),

-- Usage : tendance sur les 3 derniers mois (moyenne récente vs ancienne)
usage_par_mois AS (
    SELECT 
        u.client_id,
        u.mois,
        u.nb_connexions,
        u.volume_data_go,
        u.duree_appels_min,
        ROW_NUMBER() OVER (PARTITION BY u.client_id ORDER BY u.mois DESC) AS rn_mois
    FROM usage_mensuel u
    CROSS JOIN params pr
    WHERE u.mois BETWEEN pr.debut_periode AND pr.date_reference
),

usage_agg AS (
    SELECT 
        client_id,
        AVG(CASE WHEN rn_mois <= 3 THEN nb_connexions END) AS connexions_3derniers_mois,
        AVG(CASE WHEN rn_mois > 3 AND rn_mois <= 6 THEN nb_connexions END) AS connexions_3mois_avant,
        AVG(CASE WHEN rn_mois <= 3 THEN volume_data_go END) AS volume_go_3derniers_mois,
        SUM(nb_connexions) AS total_connexions_12_mois,
        SUM(volume_data_go) AS total_volume_go_12_mois
    FROM usage_par_mois
    GROUP BY client_id
),

-- Tenure (ancienneté) = mois depuis date_debut du dernier abonnement
clients_avec_abonnement AS (
    SELECT 
        d.client_id,
        d.date_debut,
        d.date_fin,
        d.tarif_mensuel,
        d.type_contrat,
        d.statut,
        d.categorie_produit,
        EXTRACT(YEAR FROM AGE(pr.date_reference, d.date_debut)) * 12 
            + EXTRACT(MONTH FROM AGE(pr.date_reference, d.date_debut)) AS tenure_mois
    FROM dernier_abonnement d
    CROSS JOIN params pr
    WHERE d.rn = 1
)

-- Assemblage final : une ligne par client avec toutes les features + cible churn
SELECT 
    c.client_id,
    c.date_inscription,
    c.genre,
    c.senior_citizen,
    c.partenaire,
    c.personnes_a_charge,
    c.canal_acquisition,
    c.region,
    -- Features abonnement
    ca.tenure_mois,
    ca.type_contrat,
    ca.tarif_mensuel AS charges_mensuelles,
    ca.categorie_produit,
    -- Features facturation (avec COALESCE pour les clients sans facture dans la période)
    COALESCE(af.nb_factures, 0) AS nb_factures,
    COALESCE(af.total_charges, 0) AS total_charges,
    COALESCE(af.nb_retards_paiement, 0) AS nb_retards_paiement,
    CASE 
        WHEN COALESCE(af.nb_factures, 0) = 0 THEN 0 
        ELSE COALESCE(af.nb_retards_paiement, 0)::FLOAT / af.nb_factures 
    END AS ratio_retards_paiement,
    -- Features support
    COALESCE(ast.nb_interactions_support, 0) AS nb_interactions_support,
    COALESCE(ast.nb_contacts_resiliation, 0) AS nb_contacts_resiliation,
    COALESCE(ast.taux_resolution_satisfaisante, 1) AS taux_resolution_support,
    -- Features usage et tendance
    COALESCE(ua.total_connexions_12_mois, 0) AS total_connexions_12_mois,
    COALESCE(ua.connexions_3derniers_mois, 0) AS connexions_moy_3derniers_mois,
    COALESCE(ua.connexions_3mois_avant, 0) AS connexions_moy_3mois_avant,
    -- Tendance : baisse de connexions (feature dérivée)
    CASE 
        WHEN COALESCE(ua.connexions_3mois_avant, 0) > 0 
        THEN (ua.connexions_3derniers_mois - ua.connexions_3mois_avant) / ua.connexions_3mois_avant 
        ELSE 0 
    END AS evolution_connexions_ratio,
    -- CIBLE : Churn = 1 si résilié dans la période cible (ex. dernier trimestre)
    CASE WHEN ca.statut = 'résilié' AND ca.date_fin >= pr.debut_periode THEN 1 ELSE 0 END AS churn
FROM clients c
INNER JOIN clients_avec_abonnement ca ON c.client_id = ca.client_id
CROSS JOIN params pr
LEFT JOIN agg_facturation af ON c.client_id = af.client_id
LEFT JOIN agg_support ast ON c.client_id = ast.client_id
LEFT JOIN usage_agg ua ON c.client_id = ua.client_id
ORDER BY c.client_id;
