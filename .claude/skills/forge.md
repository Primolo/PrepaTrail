# forge

Workflow complet : cadrer → construire → vérifier. Ne livre rien de bancal.

## Quand l'utiliser

Invoque `forge` (ou `/forge`) quand l'utilisateur veut construire quelque chose de nouveau ou ajouter une fonctionnalité significative. Ne l'utilise pas pour des corrections mineures ou du refactoring isolé.

## Les 3 phases — dans l'ordre, sans en sauter

### Phase 1 · SPEC — Cadrer

Avant d'écrire la moindre ligne de code :

1. Pose une seule question à la fois jusqu'à comprendre exactement ce qui est attendu.
   Couvre dans cet ordre (adapte selon les réponses) :
   - Quel problème concret est résolu ? (pas la solution — le problème)
   - Qui sont les utilisateurs ?
   - Quelle est l'entrée ? Quelle est la sortie attendue ?
   - Contraintes techniques existantes ?
   - Cas limites et scénarios d'erreur importants ?
   - Comment saura-t-on que c'est terminé ? (critères mesurables)

2. Écris `specs/projet.md` avec cette structure exacte :

```markdown
# Spec : [nom]

## Objectif
[Une phrase : quel problème, pour qui.]

## Contexte
[Ce qui existe déjà, pourquoi ce projet maintenant.]

## Besoins exacts
- [ ] Besoin 1
- [ ] Besoin 2

## Entrées / Sorties
- **Entrée** : ...
- **Sortie** : ...

## Contraintes techniques
- ...

## Cas limites
- ...

## Définition de "terminé"
- [ ] Critère 1 mesurable
- [ ] Critère 2 mesurable

## Hors périmètre
- Ce qui ne sera PAS fait dans cette version.
```

3. Montre le plan à l'utilisateur et attends sa validation explicite avant de passer à la phase suivante. Ne continue pas si le plan est flou.

---

### Phase 2 · BUILD — Construire

Une fois le plan validé :

1. Implémente **exactement** ce qui est écrit dans `specs/projet.md` — rien de plus, rien de moins.
2. Si un point est ambigu, pose **une seule question** avant de coder.
3. Respecte les contraintes techniques et gère les cas limites documentés.
4. N'ajoute aucune fonctionnalité non listée. Ne refactorise pas le code existant sauf si le plan l'exige.
5. À la fin du build, affiche :

```
## Build terminé

### Besoins couverts
- [x] Besoin 1 → fichier:ligne
- [x] Besoin 2 → fichier:ligne

### Critères "terminé" atteints
- [x] Critère 1
- [x] Critère 2

### Hors périmètre respecté
- [item] — non implémenté volontairement
```

---

### Phase 3 · REVIEW — Vérifier

Immédiatement après le build :

1. Compare le code produit avec chaque item de `specs/projet.md`.
2. Classe chaque besoin :
   - ✅ Couvert — conforme au plan
   - ❌ Manquant — pas implémenté
   - ⚠️ Partiel — incomplet ou incorrect
   - 🐛 Bug — ne fonctionne pas comme attendu

3. **Si tout est ✅** : affiche "Forge complète. Le build est conforme au plan." et arrête.

4. **Sinon** : corrige chaque item ❌ / ⚠️ / 🐛 directement dans le code, puis relance la review. Répète jusqu'à ce que tout soit ✅.

```
## Rapport de conformité

### ✅ Couverts (N)
- Besoin X → fichier:ligne

### ❌ / ⚠️ / 🐛 À corriger (N)
- **Besoin Y** : [ce qui manque ou ne va pas] → correction appliquée dans fichier:ligne

---
[Forge complète. | Corrections appliquées — nouvelle vérification en cours.]
```

## Règles absolues

- Ne passe jamais à BUILD sans plan validé dans `specs/projet.md`.
- Ne valide jamais la REVIEW si un seul item n'est pas ✅.
- Ne construis jamais au-delà du plan — chaque ligne de code doit être justifiée par un besoin écrit.
