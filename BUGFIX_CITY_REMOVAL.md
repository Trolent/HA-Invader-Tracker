# Fix: Correction de la suppression des villes comme appareils

## Problème

Lorsqu'un utilisateur supprime une ville de la configuration de l'intégration Invader Tracker, les appareils correspondants n'étaient **pas supprimés** de Home Assistant. Cela laissait des appareils orphelins dans le registre des appareils, ce qui causait une accumulation de données inutiles et une interface utilisateur confuse.

### Cause racine

Dans la fonction `async_update_options` du fichier `__init__.py`, quand les options étaient mises à jour (y compris la suppression de villes), l'intégration était simplement rechargée sans:

1. **Identifier les villes supprimées** - Pas de comparaison entre les anciennes et nouvelles villes
2. **Supprimer les appareils** - Pas d'appel au registre des appareils pour nettoyer les appareils orphelins
3. **Mettre à jour les coordinateurs** - Les coordinateurs continuaient à tracker les anciennes villes même après suppression

## Solution

### Changements implémentés

Le fichier `custom_components/invader_tracker/__init__.py` a été modifié pour:

#### 1. Détecter les villes supprimées
```python
old_cities = entry.data.get(CONF_CITIES, {})
new_cities = entry.options.get(CONF_CITIES, {})
removed_cities = set(old_cities.keys()) - set(new_cities.keys())
```

#### 2. Décharger les entités avant suppression
```python
await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

#### 3. Supprimer les appareils correspondants du registre
```python
device_registry = async_get_device_registry(hass)

for city_code in removed_cities:
    device_id = f"{entry.entry_id}_{city_code}"
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, device_id)}
    )
    if device:
        device_registry.async_remove_device(device.id)
```

#### 4. Mettre à jour les coordinateurs avec les nouvelles villes
```python
spotter_coordinator.update_cities(new_cities)
processor.set_city_names(new_cities)
```

#### 5. Recharger les entités pour les villes restantes
```python
await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
```

## Flux de suppression amélioré

1. **Détection** → Les villes supprimées sont identifiées par comparaison
2. **Déchargement** → Les entités existantes sont déchargées
3. **Nettoyage** → Les appareils orphelins sont supprimés du registre
4. **Mise à jour** → Les coordinateurs et processeurs sont mis à jour
5. **Recréation** → Les entités pour les villes restantes sont créées

## Identifier les appareils supprimés

Chaque appareil est identifié par le tuple `(DOMAIN, device_id)` où:
- `DOMAIN` = `"invader_tracker"`
- `device_id` = `f"{entry.entry_id}_{city_code}"`

Exemple: Pour une entrée avec l'ID `a1b2c3d4` et la ville `PA`, l'identifiant est:
```
(invader_tracker, "a1b2c3d4_PA")
```

## Tests

Des tests unitaires ont été créés dans `tests/test_device_removal.py` pour vérifier:

1. ✅ La suppression correcte des appareils quand une ville est supprimée
2. ✅ La gestion du cas où l'appareil n'existe pas dans le registre
3. ✅ Le fait qu'ajouter une ville ne déclenche pas de suppression
4. ✅ La mise à jour correcte des coordinateurs

## Impact sur l'utilisateur

- Les appareils supprimés disparaissent immédiatement de Home Assistant
- Aucun appareil orphelin n'est laissé
- Les entités restantes continuent de fonctionner normalement
- L'interface utilisateur reste propre et à jour
