# Historique des Pannes — Pompe P-17

Ce document recense les pannes passées, leurs causes identifiées et les actions correctives mises en place. L'agent ResilientFlow AI consulte cet historique pour affiner ses diagnostics par reconnaissance de patterns récurrents.

## Synthèse des Récurrences

| Type de panne | Occurrences | Fréquence moyenne |
|---|---|---|
| Usure roulement palier aspiration | 2 | ~18 mois |
| Fuite garniture mécanique | 1 | ~24 mois |
| Colmatage filtre | Récurrent (préventif) | Trimestriel |

## Détail des événements

### 🔴 2022-11-03 — Fuite Garniture Mécanique (Correctif)

**Contexte** : Détection d'une flaque de fluide sous la pompe lors de la ronde de surveillance. Température corps de pompe à 112°C au moment de la détection.

**Cause racine identifiée** : Garniture mécanique en fin de vie (28 mois d'utilisation, au-delà de la durée de vie théorique de 24 mois en service continu).

**Action corrective** : Remplacement garniture (réf. P17-SEAL-042). Arrêt de production de 4h.

**Leçon retenue** : Surveiller la température corps de pompe comme indicateur précoce — une montée progressive sur plusieurs jours précède généralement la fuite de 5-7 jours. **Le seuil d'alerte ResilientFlow (90°C) a été calibré à partir de cet événement.**

---

### 🟡 2024-03-07 — Usure Roulement Palier Gauche (Prédictif)

**Contexte** : L'agent de surveillance vibratoire a détecté une augmentation progressive de la vibration palier sur 12 jours (de 1,2 à 3,8 mm/s).

**Cause racine identifiée** : Usure normale du roulement 6205-2RS après ~16 000h de fonctionnement (légèrement au-delà de la durée de vie théorique de 15 000h).

**Action corrective** : Remplacement préventif du roulement avant rupture, planifié en créneau de production creux. **Aucun arrêt de production non planifié.**

**Leçon retenue** : La détection précoce (avant le seuil critique de 4,5 mm/s) a permis une intervention planifiée plutôt qu'une urgence. Validation de l'approche de maintenance prédictive.

---

### 🟢 2023-09-20 — Maintenance Trimestrielle Q3 (Préventif)

**Contexte** : Maintenance systématique programmée.

**Constat** : Filtre aspiration très encrassé (perte de charge supérieure à la normale). Origine : particules en suspension provenant d'une opération de maintenance sur la ligne amont 2 semaines auparavant.

**Action corrective** : Remplacement filtre + vérification absence d'usure prématurée sur les composants internes (aucune anomalie détectée).

**Leçon retenue** : Les opérations sur les lignes amont peuvent impacter l'encrassement du filtre P-17 — envisager un contrôle filtre après toute intervention en amont du circuit.

---

### 🟢 2021-06-14 — Maintenance Préventive Initiale (Préventif)

**Contexte** : Première maintenance majeure après mise en service (2019).

**Constat** : État général conforme. Remplacement systématique des joints et graissage selon recommandations constructeur initiales.

**Action corrective** : Opération standard, aucune anomalie.

---

## 💡 Recommandations pour l'Agent IA

Lors de l'analyse d'une alerte, prendre en compte :

1. Si **température en hausse progressive** sur plusieurs cycles → privilégier l'hypothèse garniture mécanique (précédent du 2022-11-03), recommander intervention **avant** dépassement du seuil critique
2. Si **vibration en hausse progressive** sur plusieurs jours → privilégier l'hypothèse usure roulement, intervention **prédictive planifiable** plutôt qu'urgence (précédent du 2024-03-07 — succès)
3. Si **pression élevée après opération sur ligne amont** → vérifier le filtre en priorité (précédent du 2023-09-20)
4. La pompe a dépassé sa **8ème année de service** (mise en service 2019) — surveillance accrue recommandée pour anticiper une éventuelle décision de remplacement (cf. analyse CAPEX Antoine)
