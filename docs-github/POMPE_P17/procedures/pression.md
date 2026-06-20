# Procédure : Surpression Circuit Hydraulique — Pompe P-17

## 🔍 Diagnostic

Une pression de refoulement supérieure à 7,0 bar indique généralement un **colmatage en aval** ou un **dysfonctionnement de la vanne de régulation**.

| Symptôme observé | Cause probable |
|---|---|
| Pression élevée + débit normal | Colmatage filtre aspiration ou refoulement |
| Pression élevée + débit faible | Vanne refoulement V-02 partiellement fermée |
| Pression élevée + vibration | Cavitation (problème aspiration) |
| Pression instable / oscillante | Air dans le circuit hydraulique |

## ⚠️ Niveau de Risque

**Risque Matériel** : Une surpression prolongée (> 8,5 bar) au-delà de la pression max admissible (10 bar) peut provoquer une rupture de joint ou de canalisation — projection de fluide sous pression.

**Risque Sécurité** : Projection de fluide haute pression — risque de blessure par injection (même à travers les vêtements) ou brûlure chimique selon le fluide.

## 🦺 EPI Obligatoires

- **Écran facial anti-projection** (obligatoire)
- Combinaison anti-projections étanche
- Gants résistants aux produits chimiques (selon fluide process)
- Bottes de sécurité étanches
- Lunettes de protection sous l'écran facial

## 🔒 Procédure LOTO (obligatoire avant intervention)

1. Informer l'équipe de production de l'arrêt
2. Couper l'alimentation électrique via sectionneur cellule BT n°3
3. Cadenasser le sectionneur avec cadenas personnel + étiquette
4. Fermer la vanne d'aspiration V-01
5. **⚠️ PURGE OBLIGATOIRE** : Ouvrir très progressivement le robinet de purge RP-01 (risque de jet sous pression)
6. Attendre la stabilisation à 0 bar sur le manomètre local avant toute autre opération
7. Fermer ensuite la vanne de refoulement V-02
8. Apposer la fiche de consignation

## 🔧 Étapes d'Intervention

### Si colmatage filtre :

1. Dévisser le bouchon du corps de filtre (attention au fluide résiduel)
2. Extraire la cartouche filtrante **Filtrec R160C10B**
3. Inspecter le degré d'encrassement et identifier la cause (particules en amont ?)
4. Nettoyer le corps de filtre
5. Installer une cartouche filtrante neuve
6. Remonter le bouchon avec joint neuf, serrage manuel + 1/4 de tour

### Si vanne de régulation défaillante :

1. Vérifier l'ouverture complète de la vanne V-02 (position manette)
2. Contrôler l'absence de blocage mécanique (corps étranger, corrosion)
3. Si vanne grippée : appliquer dégrippant, manoeuvrer plusieurs fois à vide
4. Si défaut persistant : remplacement vanne (intervention spécialisée — contacter Sophie)

### Si cavitation suspectée :

1. Vérifier le niveau du réservoir/bac d'aspiration
2. Vérifier l'absence d'obstruction sur la crépine d'aspiration
3. Contrôler la hauteur géométrique d'aspiration (NPSH disponible)

## ✅ Remise en Service

1. Retirer la consignation LOTO
2. Fermer le robinet de purge RP-01
3. Réouvrir progressivement V-01 puis V-02
4. Réarmer le sectionneur
5. Démarrage — purger l'air éventuel via le purgeur haut point
6. Surveillance pression pendant 10 minutes
7. **Critère de validation** : pression stabilisée entre 4,0 et 6,0 bar (plage nominale)
8. Informer la production

## 📦 Pièces Nécessaires

| Pièce | Référence | Quantité | Emplacement Magasin |
|---|---|---|---|
| Cartouche filtrante 50 microns | Filtrec R160C10B | 1 | Allée D2 - Étagère 3 |
| Joint bouchon filtre | — (fourni avec cartouche) | 1 | Allée D2 - Étagère 3 |

## ⏱️ Durée Estimée

**1 à 2 heures** selon la cause identifiée (filtre = rapide, vanne = peut nécessiter escalade)

## 📞 En cas de doute

Si la pression reste anormale après remplacement du filtre, **ne pas forcer la vanne V-02**. Contacter Sophie pour planifier une intervention sur la vanne de régulation avec un technicien spécialisé hydraulique.
