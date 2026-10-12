# Plan de nettoyage Cyclistic — version 3.2

| | |
|---|---|
| Statut | **Document préparatoire, en attente de validation explicite avant toute préparation des données.** Aucun nettoyage, aucune table nettoyée, aucune modification de la base. |
| Version | v3.2 (2026-10-11, mission 4.4). Intègre les décisions D1 à D6 rendues sur la revue `reports/revue_plan_v3.1.md`. Les versions **v3** (`docs/plan_nettoyage.md`) et **v3.1** (`docs/plan_nettoyage_v3.1.md`) sont **conservées intactes**. |
| Données | `raw.trips` (6 171 785 lignes, fidélité démontrée par empreinte exhaustive, audit 4.1) et `raw.source_files`, **en lecture seule pendant tout le nettoyage**. CSV et ZIP sources inchangés. |
| Références | voir §8 (inventaire de traçabilité) |

Légende :
- **[M]** : fait mesuré ;
- **[D]** : fait documentaire (source citée) ;
- **[H]** : hypothèse ;
- **[R]** : règle ou recommandation ;
- ⚑ : nouveau ou modifié par rapport à la v3.1.

---

## 0. Décisions enregistrées et changements v3.1 → v3.2

| Décision | Statut (mission 4.4) | Traduction dans la v3.2 |
|---|---|---|
| D1 — Espaces en bordure | **Approuvée** | R8 devient une règle ferme : seul l'espace ordinaire est retiré, en début et en fin des 4 champs de station. Valeur brute dans `raw`, indicateur, journal, contrôles avant/après (Q20). |
| D2 — Espaces internes | **Approuvée** | R8 : les espaces doubles internes sont préservés, sauf nouvelle justification documentée. Q20 vérifie leur préservation. |
| D3 — Limite mars-avril | **Approuvée** | R1 inchangée. F14 et L2 présentent la fourchette comme une **estimation par analogie**. Mention obligatoire dans le rapport final (§10). Sensibilité SENS-2. |
| D4 — Identifiant de station | **Approuvée sous réserve** | R11 : l'ID est la clé des analyses par station **quand il est présent et suffisamment cohérent** (critère proposé en §11, P-2). Contrôles S1–S6. **Aucune fusion par le nom.** Analyses géographiques séparées. |
| D5 — Seuil de 60 s | **Approuvée comme choix provisoire**, sensibilité obligatoire | R4 inchangée. SENS-1 obligatoire, par type de vélo et par type d'usager. Documentation citée avec ses limites (F12, F21). |
| D6 — Stations de test ou de personnel | **Non approuvée** | **Aucune exclusion, aucun indicateur** dans les données nettoyées. Examen documenté en §5. Seul un contrôle de suivi (S5), qui produit un rapport, est prévu. |

**Corrections techniques retenues :** T-1 à T-6 (§8). T-7 fait l'objet d'une procédure séparée, **non exécutée** (§9).

---

## 1. Faits mesurés et documentaires

| # | Fait | Source |
|---|---|---|
| F1 | 6 171 785 lignes, 12 CSV, 13 colonnes identiques, aucune ligne mal formée, aucun `ride_id` vide. Fidélité de `raw.trips` démontrée sur toutes les lignes (12/12 empreintes). | [M] missions 2, 4, audit 4.1 |
| F2 | 6 171 750 `ride_id` distincts. 35 identifiants apparaissent exactement 2 fois (une fois dans `202604`, une fois dans `202605`). **Les 70 lignes sont conservées dans `raw.trips`.** Contenus identiques sur les 13 colonnes. Ce sont tous des trajets du 30/04/2026 au 01/05/2026. | [M] audit 4.1 |
| F3 | Pour 10 limites de mois sur 12, les trajets à cheval sur deux mois sont rattachés une seule fois, au fichier du mois d'arrivée. Le fichier `202604` suit le mois de départ. | [M] audit 4.1 |
| F4 | 71 trajets commencés en septembre 2025 sont hors période. Les trajets commencés le 30/09/2026 et terminés en octobre sont absents (fichier `202610` non publié) : **environ 25 à 90, estimation par analogie**. | [M] + [H] mesure 4.2 |
| F5 | Le CSV de l'archive `202601` s'appelle `202501-divvy-tripdata.csv` ; son contenu est bien de janvier 2026. | [M] |
| F6 | Horodatages en heure locale, sans fuseau. Aucun dans l'heure inexistante du 08/03/2026. | [M] |
| F7 | Durées : 29 négatives (toutes le 02/11/2025 entre 01h et 02h) ; **0 nulle** ; 159 192 positives de moins de 60 s. Aucun recouvrement avec les doublons ou les trajets hors période. | [M] missions 3, 4.3 |
| F8 | 474 trajets conservés chevauchent l'heure ambiguë du 02/11/2025 ; 40 enjambent l'heure sautée du 08/03/2026. | [M] |
| F9 | 5 451 lignes brutes sans coordonnées d'arrivée (5 432 conservées). 5 304 trajets de plus de 24 h conservés. | [M] |
| F10 | Stations manquantes (nom et ID toujours ensemble) : 1 289 486 au départ, 1 355 487 à l'arrivée (brut). | [M] |
| F11 | `rideable_type` ∈ {classic_bike, electric_bike} ; `member_casual` ∈ {member, casual} ; coordonnées dans la zone de Chicago. | [M] |
| F12 ⚑ | **Documentation du seuil :** la page « System Data » de Divvy (https://divvybikes.com/system-data, consultée le 2026-10-11) indique que les données ont été traitées pour retirer les trajets du personnel et « any trips that were below 60 seconds in length », présentés comme de possibles faux départs ou re-verrouillages. | [D] |
| F13 | R4b retire 3,40 % des lignes brutes des occasionnels et 2,13 % de celles des membres. | [M] |
| F14 ⚑ | Aucun trajet ne franchit la limite du 31/03/2026 au 01/04/2026. Par analogie avec 10 autres limites (0,25 % à 0,91 % des départs du dernier jour), on en attendrait **environ 28 à 102 (médiane 61). C'est une estimation par analogie, pas un nombre mesuré de trajets manquants.** Méthode, hypothèses et limites : revue 4.3, §2.3. | [M] + [H] |
| F15 | Espaces en bordure, uniquement l'espace ordinaire (U+0020). Noms : espace final (10 valeurs au départ, 34 541 lignes ; 11 à l'arrivée, 36 756 lignes). ID : espace initial sur `␠CHI02331` seulement (643 et 587 lignes, fichiers `202605` et `202606`). 0 valeur faite uniquement d'espaces. | [M] |
| F16 | Horodatages à exactement 3 décimales. L'affichage d'un `timestamp` supprime les zéros finaux (618 472 et 617 385 valeurs) **sans changer la valeur**. | [M] audit 4.1 |
| F17 ⚑ | Après suppression des espaces en bordure : 55 ID de départ et 53 ID d'arrivée ont plusieurs noms (7 variantes triviales par côté). 60 et 59 noms ont plusieurs ID. 6 ID de départ sur 1 181 (vélos classiques) ont des coordonnées étalées sur plus de 0,005°. Exemple substantiel : `CHI00295` = « Dearborn St & Erie St » et « Wells St & Ohio St ». | [M] revue 4.3 |
| F18 ⚑ | **Les 159 192 trajets positifs de moins de 60 s sont tous des `electric_bike`** (member 84 724, casual 74 468) ; **0 `classic_bike`**. Parmi eux : même station au départ et à l'arrivée 45 028, au moins une station absente 110 742, deux stations différentes 3 422. Taux R4b : 3,63 % des électriques bruts, 0 % des classiques. Parmi les électriques : 4,54 % des occasionnels, 3,08 % des membres. | [M] revue 4.3 |
| F19 ⚑ | 42 lignes brutes (41 conservées après R1, R2 et R4) touchent une station dont le nom évoque un usage interne (entrepôt, test, réparation, recharge). Détail en §5. | [M] mission 4.4 |
| F20 ⚑ | Flux public des stations de Divvy (GBFS `station_information`, instantané du 2026-10-11 à 13:43 UTC, 2 075 stations) : **aucune** des stations de F19 n'y figure. `CHI02331` y est « Franklin St & Randolph St ». | [D] mission 4.4 |
| F21 ⚑ | **Limites d'applicabilité de F12 aux fichiers actuels :** la même page décrit des catégories d'usagers d'un ancien format (adhésion, trajet unique, pass journée), pas `member` / `casual`. Elle déclare retirer les trajets du personnel, alors que F19 en suggère la présence. Et les moins de 60 s subsistent, uniquement pour les vélos électriques (F18). **[H]** Le filtre de l'éditeur semble encore appliqué aux vélos classiques seulement. | [D] + [M] + [H] |

## 2. Exigences du PDF (inchangées)

| # | Exigence |
|---|---|
| P1 | 12 derniers mois de données. |
| P2 | Garder une copie des données d'origine. |
| P3 | `ride_length` = `ended_at − started_at`, au format HH:MM:SS. |
| P4 | `day_of_week` : 1 = dimanche … 7 = samedi. |
| P5 | Colonnes cohérentes, vue annuelle unique. |
| P6 | Vérifier l'intégrité et documenter le nettoyage. |
| P7 | Pas de données personnelles (PII) ; licence Motivate International Inc. |

## 3. Règles

**Principes communs [R] :**
- `raw.*` n'est jamais modifié.
- Exclusions de base dans l'ordre R2 → R1 → R4a → R4b, avec un seul motif par ligne. Les motifs sont **disjoints** (mesure 4.3) : l'ordre n'a pas d'effet sur les comptes.
- Les indicateurs et normalisations n'excluent aucune ligne.
- **Aucune exclusion propre à une analyse n'est appliquée à `clean.trips`.**

| Règle | Contenu | Contrôles |
|---|---|---|
| **R1 Période** | `started_at::timestamp` ∈ [2025-10-01 00:00, 2026-10-01 00:00), heure locale ; `ride_month = date_trunc('month', started_at)`. Ni le nom de fichier, ni F3, F4 ou F14 n'interviennent. Aucune reconstitution. | Q4–Q7, SENS-2 |
| **R2 Doublons** | (1) Contrôle bloquant : même `ride_id` avec un contenu différent → arrêt + `audit.ride_id_conflicts`. (2) On garde la première occurrence par (`file_month`, `source_line`), soit les 35 lignes de `202604`. (3) Les 35 lignes de `202605` sont exclues avec le motif `duplicate_ride_id`. Le journal garde : `source_csv`, `source_line`, `ride_id`, `kept_source_csv`, `kept_source_line`, et l'empreinte MD5 du contenu exclu et du contenu gardé. | Q2, Q3, Q8, Q9, Q22 |
| **R3 Horodatages et durées** ⚑ T-1 | `clean.started_at` et `ended_at` sont de type `timestamp`, obtenus par conversion directe ; **les chaînes source restent dans `raw.trips`**. `ride_length` et `ride_length_sec` sont calculés à partir des horodatages bruts. `day_of_week = EXTRACT(DOW)+1`. Changements d'heure : indicateurs `dst_fall_back_overlap` (474) et `dst_spring_forward_span` (40). **Aucune correction automatique de l'heure d'automne.** Pour l'heure d'été, une colonne séparée `ride_length_sec_dst_adj` n'est corrigée que si les 4 critères individuels sont vérifiés (v3, R3), avec `dst_adj_status` et une comparaison avec et sans correction. **Aucune correction n'est appliquée dans la mission 4.4.** | Q10 (valeurs), Q11, Q12, Q12b |
| **R4 Durées courtes** | R4a : `ride_length_sec < 0` → `negative_duration` (29). R4b : `0 ≤ ride_length_sec < 60` → `under_60s` (159 192, dont 0 nulle). **Choix provisoire** (D5) : la règle s'appuie sur F12 et ses limites sont décrites en F21. Sensibilité SENS-1 obligatoire. | Q9, Q13, SENS-1 |
| **R5 Arrivées manquantes** | Trajets conservés dans `clean.trips`, `has_end_location = false` (5 432). Sous-ensembles d'analyse sous forme de vues (§6.2). | Q14, Q15 |
| **R6 Longues durées** | Aucun plafond ; `is_over_24h` (5 304) ; statistiques robustes ; moyenne sur 3 périmètres. | Q16 |
| **R7 Stations manquantes** ⚑ T-3 | Déjà `NULL` dans `raw` (0 `''`), aucune conversion ; aucune imputation ; `start_station_missing` / `end_station_missing`. | Q17 |
| **R8 Espaces** ⚑ D1, D2 | `btrim(valeur, ' ')` (espace U+0020 uniquement) sur `start_station_name`, `start_station_id`, `end_station_name`, `end_station_id`. **Espaces internes préservés.** Indicateurs `*_trimmed`. Journal `audit.normalization_log` au niveau des valeurs (colonne, valeur brute, valeur normalisée, lignes, fusion avec une valeur existante oui/non). Arrêt si une normalisation produit `''`. | Q17, Q20 |
| **R9 Types et domaines** | `CHECK` sur les catégories ; zone de Chicago ; `NOT NULL` sur les champs indispensables. | Q18 |
| **R10 Traçabilité** ⚑ T-4, T-5 | Lien de chaque ligne de `clean.trips` vers `raw.trips` par `(source_csv, source_line)`, avec **clé étrangère** vers la clé primaire de `raw.trips`. Tables `audit.excluded_rows`, `ride_id_conflicts`, `normalization_log`, `transform_log`, `qa_results`. Table de provenance des fichiers : **`raw.source_files`** (existante). Journaux persistants et empreintes des scripts (§8). | Q1–Q3, Q19 |
| **R11 Clé de station** ⚑ D4 | Analyses **par station** : clé = ID normalisé (R8), seulement pour les lignes avec ID, et seulement pour les ID jugés « suffisamment cohérents » selon le critère en attente (P-2). Les autres sont présentés à part, avec une mention. Nom affiché : le nom le plus fréquent de l'ID. **Aucune fusion de stations sur la base du nom.** Analyses **géographiques** : coordonnées (départ 100 % ; arrivée 6 007 026 lignes), grille d'au moins 0,01° (environ 1 km), indépendantes des ID. | S1–S6 |

## 4. Valeurs brutes et normalisées des stations

**Approche retenue [R] :**
- valeurs source **uniquement dans `raw.trips`** ;
- valeurs normalisées dans `clean.trips` ;
- traçabilité assurée par trois éléments :
  1. `clean.trips(source_csv, source_line)`, avec une clé étrangère vers `raw.trips` ;
  2. les indicateurs `*_trimmed` par ligne ;
  3. `audit.normalization_log` au niveau des valeurs : 10 + 11 + 1 + 1 valeurs attendues sur les lignes brutes.

| Avantages | Limites |
|---|---|
| Une seule source de vérité pour les valeurs brutes, sans dupliquer environ 6 millions de chaînes. | `clean.trips` n'est pas autonome : pour montrer la valeur brute, il faut une jointure avec `raw.trips`. |
| `raw` reste immuable ; la clé étrangère garantit qu'aucune ligne propre ne perd son origine. | Si `raw` était modifié ou supprimé, la trace serait perdue. Q1 le détecte, et T-7 permettrait de l'empêcher. |
| Le journal par valeur rend la normalisation auditable d'un coup d'œil (23 correspondances). | Un export de `clean` (par exemple vers Tableau) ne contient pas la valeur brute, sauf si l'export ajoute la jointure ou le journal. |
| Les indicateurs permettent d'isoler les lignes modifiées sans recalcul. | La jointure par `(source_csv, source_line)` a un coût sur 6 millions de lignes ; c'est acceptable grâce aux clés primaires indexées. |

Si un export autonome devenait nécessaire, des colonnes `*_raw` pourraient être ajoutées plus tard **à la seule demande**, sans changer la logique.

## 5. Stations de test ou de personnel : examen (D6 non approuvée)

**Critère d'identification utilisé (mesure, pas règle) :** motif `test|charging|warehouse|divvy|lbs-wh|hubbard bike|repair|valet|base` (insensible à la casse) sur les noms de station. Ce critère est **purement lexical**.

| ID | Nom | Lignes brutes où la station apparaît | Présente dans le GBFS du 2026-10-11 |
|---|---|---:|---|
| CHI02009 | STAFF & VISITORS @ West Chicago Warehouse | 34 lignes | non |
| CHI02362 | Hastings Test Station | 4 occurrences (3 lignes) | non |
| CHI02331 | Hastings Test Station (ID par ailleurs nommé « Franklin St & Randolph St ») | 2 occurrences (2 lignes) | sous le nom « Franklin St & Randolph St » |
| CHI00324 | WEST - CHI␠␠PILLAR CHARGING␠␠(CHARGING PILLAR TEST) | 2 | non |
| CHI02030 | WEST - CHI - CASSETTE REPAIR | 1 | non |

**Profil agrégé des 42 lignes [M] :**
- **Statut :** 41 conservées par R1, R2 et R4 ; 1 déjà exclue par R4b (50 s).
- **Fichiers :** `202605` (4), `202606` (4), `202608` (15), `202609` (19). Rien avant mai 2026.
- **Sens :** arrivée seule 26, départ seul 13, départ et arrivée 3.
- **Lignes conservées :** member 38, casual 3 ; classic_bike 17, electric_bike 24. Durées de 84 s à 5 238 s.
- **Rythme :** la majorité des trajets vers l'entrepôt commencent le matin (vers 08:00–10:00), et ceux qui en partent en fin d'après-midi. Un même itinéraire revient sur plusieurs jours.

**Confidentialité [R] :** ce rythme régulier pourrait permettre de reconnaître des personnes (P7). **Le détail ligne à ligne (identifiants, heures) n'est donc pas reproduit dans ce document.** Il reste retrouvable à la demande par le contrôle S5 (requête sur `raw.trips` avec le critère ci-dessus, résultat non publié).

**Ce qui permettrait de conclure à une exclusion justifiée :**
1. une confirmation de l'éditeur (Divvy/Lyft) que ces ID désignent des emplacements internes, non ouverts au public, et que les trajets associés sont des trajets de personnel ou de test ;
2. ou un historique du flux GBFS couvrant mai à septembre 2026, montrant que ces stations n'étaient pas publiques.

L'instantané actuel (F20) n'est qu'un **indice** : une absence aujourd'hui ne prouve pas le statut passé. La documentation F12 dit que les trajets du personnel sont retirés, mais F21 montre que ce n'est pas vérifié pour ces fichiers. Enfin, ces trajets portent la catégorie `member` ou `casual` : un membre du personnel peut utiliser un compte ordinaire. Exclure ces lignes pourrait donc retirer de vrais trajets de membres.

**Statut :** aucune exclusion, aucun indicateur dans `clean.trips`. Seul S5 produit une liste de suivi. Décision P-1 en attente (§11).

## 6. Bilan des lignes

### 6.1 Exclusions de base (`clean.trips`)

| Étape | Motif | Exclues | Restantes |
|---|---|---:|---:|
| 0 | brut | — | 6 171 785 |
| 1 | `duplicate_ride_id` (occurrences en trop) | 35 | 6 171 750 |
| 2 | `out_of_period` | 71 | 6 171 679 |
| 3 | `negative_duration` | 29 | 6 171 650 |
| 4 | `under_60s` | 159 192 | **6 012 458** |
| | **Total exclu** | **159 327** | |

**Vérification :**
- 35 + 71 + 29 + 159 192 = 159 327 ;
- 6 171 785 − 159 327 = **6 012 458** ✔ ;
- en testant les critères séparément, on obtient les combinaisons {aucun : 6 012 458 ; < 60 s seul : 159 192 ; hors période seul : 71 ; doublon seul : 35 ; négatif seul : 29}. **Aucune ligne n'a deux motifs** [M, revue 4.3].

**Ce bilan ne change pas avec D1, D2, D3, D4, ni avec D6** dans son état actuel (non approuvée).

Conservés par mois : 2025-10 : 629 080 · 11 : 346 963 · 12 : 136 584 · 2026-01 : 133 936 · 02 : 197 432 · 03 : 308 729 · 04 : 435 832 · 05 : 635 978 · 06 : 742 079 · 07 : 846 786 · 08 : 847 158 · 09 : 751 901. Par type d'usager : member 3 897 958 ; casual 2 114 500.

### 6.2 Sous-ensembles propres à certaines analyses (pas des suppressions)

| Sous-ensemble | Lignes | Nature |
|---|---:|---|
| `clean.trips` (général) | 6 012 458 | [M] |
| avec coordonnées d'arrivée (`v_trips_geo`) | 6 007 026 | [M] |
| sans coordonnées d'arrivée (**conservés**) | 5 432 | [M] |
| avec station de départ / d'arrivée | 4 810 563 / 4 761 786 | calculé |
| avec les deux stations | 4 049 494 | [M] |
| sans nom ni ID de station (**conservés**) | 1 201 895 (départ) / 1 250 672 (arrivée) | [M] |
| SENS-1 (+ positifs < 60 s) | 6 171 650 | calculé |
| SENS-2 (− 31/03 et 01/04) | à mesurer | — |
| S5 (stations de test ou de personnel, suivi) | 41 | [M] |

**Les trajets sans coordonnées d'arrivée ou sans station ne sont jamais supprimés globalement.** Ils ne sont écartés que des vues qui exigent ces champs, et la couverture de chaque vue est publiée (Q15).

## 7. Contrôles qualité et sensibilités

| # | Contrôle | Attendu |
|---|---|---|
| Q1 | SHA-256 des 24 sources = `raw.source_files` ; empreinte exhaustive de `raw.trips` = audit 4.1 | identiques |
| Q2 | `raw` = `clean` + exclusions | 6 171 785 = 6 012 458 + 159 327 |
| Q3 | Chaque ligne brute dans exactement un état ; clé étrangère de `clean` vers `raw` respectée | 0 / 0 |
| Q4–Q7 | Période, 12 mois et comptes, mois indépendant du fichier, cas `202501` | conformes |
| Q8 | Unicité de `ride_id` ; conflits = 0 | vrai |
| Q9 | Un motif par exclusion ; comptes | 35 / 71 / 29 / 159 192 |
| **Q10** ⚑ | `clean.started_at = raw.started_at::timestamp` et idem pour `ended_at` (jointure par provenance) ; complément : `to_char(clean.started_at, 'YYYY-MM-DD HH24:MI:SS.MS') = raw.started_at`. **Aucune comparaison de `::text`.** | 0 différence |
| Q11 | `ride_length_sec`, `day_of_week` ; 2025-10-05 → 1 | 0 écart |
| Q12 / Q12b | Indicateurs de changement d'heure (474 / 40) ; correction séparée de l'heure d'été conforme ; 0 correction pour l'heure d'automne | conformes |
| Q13 | `min(ride_length_sec) ≥ 60` ; motifs R4a et R4b cohérents avec le signe | vrai |
| Q14 / Q15 | 5 432 sans arrivée conservés ; couverture des vues | égalité |
| Q16 | 5 304 trajets de plus de 24 h conservés | vrai |
| **Q17** ⚑ | 0 `''` ; nom NULL ⇔ ID NULL ; pour les valeurs non NULL : `clean = btrim(raw, ' ')` (D1 approuvée) | vrai |
| Q18 | Domaines | 0 violation |
| Q19 | Chaînage du journal des étapes | vrai |
| **Q20** ⚑ | **Avant :** nombre de valeurs avec espace en bordure par colonne, sur les lignes conservées. **Après :** 0 en bordure. Indicateurs `*_trimmed` = compte « avant ». Valeurs distinctes avant/après et fusions = journal (fusions attendues : `Sheffield Ave & Addison St`, `CHI02331`). **0 `''` produite. Espaces internes inchangés** (même nombre d'espaces après `btrim`). | conforme |
| Q21 | Limite mars-avril : 0 trajet de mars terminé en avril, enregistré comme **anomalie connue** et non comme un échec | 0 (connu) |
| Q22 | Provenance du dédoublonnage : 35 exclus de `202605`, gardés de `202604`, empreintes égales | 35 / 35 / 0 |
| S1 | ID à plusieurs noms (triviaux / substantiels) | 55 / 53 (avec 7 / 7 triviaux), liste publiée |
| S2 | Noms à plusieurs ID | 60 / 59, liste publiée |
| S3 | Étendue des coordonnées par ID (vélos classiques) > 0,005° | 6, liste publiée |
| S4 | Nom dominant par ID et par mois (renommage ou ambiguïté) | tableau publié |
| S5 | Stations de test ou de personnel (critère lexical §5) | 41 lignes conservées ; **rapport non nominatif, aucune exclusion** |
| S6 | Nom NULL ⇔ ID NULL ; aucun ID vide après `btrim` | 0 / 0 |
| **SENS-1** ⚑ (D5) | Principal (6 012 458) contre principal + positifs < 60 s (6 171 650). Indicateurs : volumes et parts, durée médiane et moyenne, répartition par jour et par heure. Ventilés **par `rideable_type` × `member_casual`**. Les négatifs restent exclus des deux côtés. | tableau d'écarts publié |
| **SENS-2** ⚑ (D3) | Indicateurs clés avec et sans les 31/03 et 01/04 | écarts publiés |

## 8. Corrections techniques et traçabilité

### 8.1 Corrections T-1 à T-6

| # | Correction | Type | Statut |
|---|---|---|---|
| T-1 | Q10 compare des valeurs `timestamp` ; chaînes source conservées dans `raw` | **document** (plan) + **code** à écrire (`sql/03_qa.sql`) | document : fait dans la v3.2 ; code : proposé (C4) |
| T-2 | F3 corrigé (convention du fichier d'avril) | document | fait (v3.1, repris en v3.2) |
| T-3 | R7 : déjà `NULL`, aucune conversion | document | fait |
| T-4 | `raw.source_files` au lieu de `audit.source_files` ; clé étrangère de `clean` vers `raw` | document + code à écrire (C3) | document : fait ; code : proposé |
| T-5 | Journaux d'exécution persistants + empreintes des scripts | **code** à écrire (C1) | proposé |
| T-6 | Archivage du script de profilage de la mission 3 et de `before.sha` | **archivage de fichiers** | **fait** (§8.3) |

### 8.2 Changements de code proposés (non réalisés)

| # | Fichier | Changement | Lien |
|---|---|---|---|
| C1 | `scripts/runlog.py` (nouveau) | Fonction utilisée par tous les scripts : écrit `reports/logs/<étape>_<AAAAMMJJ-HHMMSS>.log` (sortie console, heure de début et de fin, code de sortie) ; enregistre au début les SHA-256 des scripts et fichiers SQL utilisés ; n'enregistre aucun secret. | T-5 |
| C2 | `scripts/pg.py` | Option `read_only=True` (`PGOPTIONS=-c default_transaction_read_only=on`) pour les étapes de lecture ; journalisation des requêtes envoyées (texte SQL, durée), sans paramètres sensibles. | T-5 |
| C3 | `sql/02_clean.sql` (nouveau) | Schémas `clean` et `audit` ; contrôle des conflits ; conversion des types ; cascade R2 → R1 → R4a → R4b vers `audit.excluded_rows` ; R3, R5–R8, R11 ; clé étrangère `(source_csv, source_line)` vers `raw.trips` ; vues ; `audit.normalization_log`. | T-4, R1–R11 |
| C4 | `sql/03_qa.sql` + `scripts/run_qa.py` (nouveaux) | Q1–Q22, S1–S6. Q10 en comparaison de valeurs. Q1 réutilise le bloc `fingerprint` de `sql/audit_import.sql` et compare aux 12 sommes de `reports/audit_import_output.txt`. | T-1 |
| C5 | `sql/04_sensitivity.sql` (nouveau) | SENS-1, SENS-2. | D3, D5 |

Ces fichiers ne seront écrits qu'après votre validation (P-4).

### 8.3 Inventaire de traçabilité : fichiers historiques

| Élément | État | Emplacement | Preuve |
|---|---|---|---|
| Script de profilage de la mission 3 | **retrouvé et archivé** (copie identique, date d'origine conservée : 2026-10-11 12:46:46) | `scripts/archive/profile_mission3.py` | SHA-256 `dcb20…a9b92`, identique à l'original |
| `before.sha` (empreintes d'avant l'import, mission 2) | **retrouvé et archivé** (copie identique, 2026-10-11 12:26:02) | `reports/archive/before_mission2.sha` | SHA-256 `41f4a…618fa`, identique ; 24 empreintes = `raw.source_files` (audit 4.1, V14) |
| Script de la cascade attendue (mission 3) | déjà dans le projet | `scripts/mesure_cascade_attendue.py` | identique à l'original du dossier temporaire, **à l'exception d'un en-tête de 3 lignes ajouté** lors de l'archivage (vérifié par `diff`) |
| Code de mesure de la revue 4.3 (M1, M2) | **indisponible sous forme de fichier** : passé en entrée standard, jamais enregistré | — | Non archivé, conformément à la consigne. La logique est décrite en annexe A de la revue 4.3. Conséquence : les chiffres F17–F18 ne sont **pas reproductibles depuis un script du projet**. Ils pourront être recalculés par S1–S3 et SENS-1 lors du contrôle qualité du nettoyage. |
| Code de l'examen D6 (mission 4.4) | même situation (entrée standard) | — | Recalculable par S5 |
| Version de `scripts/pg.py` utilisée pendant l'import | **perdue** (modifiée après l'import, pas de gestion de versions) | — | Compensé par la preuve d'empreinte exhaustive (rapport d'import, T2) |
| Journal console de l'import et de la 1ʳᵉ exécution des contrôles | **non persistant** | — | Compensé partiellement par le journal du serveur (13:33:22) ; T-5 prévient la répétition |
| Autres fichiers temporaires encore présents : `verify.py`, `dates.py` (mission 1), `cascade.py` (original), `list.xml`, `keys.txt`, `index.html` (liste du bucket S3) | présents dans le dossier temporaire, **non archivés** (hors périmètre de la mission) | dossier temporaire de session | archivage possible sur décision (P-6) ; disparition possible à la fin de la session |

## 9. Procédure T-7 : rôle en lecture seule sur `raw` (**non exécutée**)

**Pourquoi :** `postgres` est superutilisateur et contourne tous les droits. Seul un rôle sans privilèges particuliers peut être réellement empêché d'écrire dans `raw`.

**Procédure proposée** (à exécuter par vous, en tant que `postgres`, après approbation explicite) :
```sql
-- 1. Rôle dédié, sans privilèges particuliers
CREATE ROLE cyclistic_etl LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\password cyclistic_etl          -- saisie interactive : jamais dans un fichier ni un script
-- 2. Accès à la base
REVOKE ALL ON DATABASE cyclistic FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE cyclistic TO cyclistic_etl;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- 3. Lecture seule sur raw (les tables restent la propriété de postgres)
GRANT USAGE ON SCHEMA raw TO cyclistic_etl;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO cyclistic_etl;
-- 4. Espaces de travail du nettoyage (crée des schémas : à approuver avec le nettoyage)
CREATE SCHEMA clean AUTHORIZATION cyclistic_etl;
CREATE SCHEMA audit AUTHORIZATION cyclistic_etl;
```

**Vérification**, en tant que `cyclistic_etl`, à l'intérieur d'une transaction annulée ensuite :
- `INSERT`, `UPDATE`, `DELETE` et `TRUNCATE` sur `raw.trips`, ainsi que `ALTER` et `DROP TABLE raw.trips`, doivent tous échouer (`permission denied` ou `must be owner`) ;
- `SELECT count(*) FROM raw.trips` doit renvoyer 6 171 785.

**Retour arrière :** `DROP OWNED BY cyclistic_etl; DROP ROLE cyclistic_etl;`. Attention : la première commande supprime aussi les schémas `clean` et `audit` appartenant au rôle.

**Effets et limites :**
- l'authentification `scram-sha-256` exige un mot de passe pour ce rôle ; on peut reprendre la saisie masquée existante en définissant `PGUSER=cyclistic_etl` ;
- `postgres` garde la possibilité de modifier `raw`, mais Q1 détecterait toute modification ;
- cette procédure **modifie les rôles et les droits** : elle n'est pas exécutée pendant la mission 4.4.

## 10. Limites à mentionner dans l'analyse

| # | Limite | Formulation à reprendre |
|---|---|---|
| L1 | Fin de période | « Les trajets commencés le 30/09/2026 et terminés en octobre ne sont pas encore publiés (environ 25 à 90, estimation par analogie). » |
| L2 ⚑ | Limite mars-avril (D3) | « Aucun trajet du jeu de données ne commence le 31 mars 2026 pour se terminer le 1er avril 2026, alors que chaque autre limite de mois complète en compte entre 12 et 173. Cette absence est probablement liée à la manière dont la source a réparti ces trajets entre les fichiers de mars et d'avril, mais elle ne peut pas être vérifiée. Par analogie avec les autres mois, l'ordre de grandeur concerné serait de quelques dizaines de trajets (environ 28 à 102, **estimation non mesurée**), soit moins de 0,002 % des trajets analysés. Aucune donnée n'a été reconstituée et la période d'analyse n'a pas été modifiée. [Résultat de SENS-2.] » |
| L3 | Changements d'heure | 474 trajets non corrigés (heure d'automne) ; 40 avec une correction séparée (heure d'été), comparaison publiée |
| L4 | Stations manquantes | environ 20 % des trajets conservés, surtout des vélos électriques |
| L5 ⚑ | Clé de station | ID ambigus (S1–S4) signalés dans les classements ; aucune fusion par le nom |
| L6 ⚑ | Seuil de 60 s | choix provisoire fondé sur la documentation de l'éditeur (F12), d'applicabilité incertaine (F21) ; il ne touche que les vélos électriques (F18) ; résultats de SENS-1 publiés |
| L7 ⚑ | Stations de test ou de personnel | 41 trajets conservés faute de règle validée (§5) |

## 11. Décisions toujours en attente

| # | Question | Options | Recommandation | Conséquences | Contrôle |
|---|---|---|---|---|---|
| **P-1** | D6 : quelle règle pour les stations de test ou de personnel ? | (a) aucune action ; (b) indicateur sans exclusion ; (c) exclusion avec le motif `staff_or_test_station`, **seulement avec une source** (§5) | **(b)** dès maintenant si vous l'acceptez ; (c) seulement après confirmation par l'éditeur ou un historique GBFS | (a), (b) : 6 012 458 lignes ; (c) : 6 012 417 (−41) | S5 |
| **P-2** | D4 : critère d'un ID « suffisamment cohérent » | (a) un seul nom, ou seulement des variantes triviales, **et** étendue spatiale ≤ 0,005° ; (b) (a) + nom dominant ≥ 90 % des lignes ; (c) aucun critère, signalement seul | **(a)** : simple et mesurable ; les ID non conformes sont analysés à part, avec une mention | aucune ligne retirée ; classements limités aux ID cohérents | S1, S3, S4 |
| **P-3** | T-7 : créer le rôle `cyclistic_etl` | exécuter la procédure §9 / ne pas l'exécuter (détection par Q1 seulement) | à votre convenance ; l'exécuter **avant** le nettoyage si vous la souhaitez | modifie les rôles et les droits ; aucun effet sur les lignes | vérification §9 |
| **P-4** | Écrire le code C1–C5 | approuver / modifier | approuver : c'est la condition des journaux persistants (T-5) et de Q10 corrigé (T-1) | création de scripts ; aucune donnée touchée | relecture du code avant exécution |
| **P-5** | Lancer la préparation des données (exécution de C3 puis C4) | — | après P-1 à P-4 | création de `clean` et `audit` ; aucune modification de `raw` | Q1–Q22, S1–S6 |
| **P-6** | Archiver les autres fichiers temporaires (`verify.py`, `dates.py`, `cascade.py` original, liste S3) | archiver / ignorer | archiver (coût nul, traçabilité des missions 1 et 2) | aucun | égalité des empreintes |
| **P-7** | Réécrire comme script documenté le code de mesure de la revue 4.3 et de l'examen D6 | écrire un **nouveau** script (pas une archive) / s'en remettre à S1–S5 | s'en remettre à S1–S5 lors du contrôle qualité (aucune duplication) | aucun | S1–S5 |

**Aucune préparation des données ne sera lancée sans votre validation explicite.**
