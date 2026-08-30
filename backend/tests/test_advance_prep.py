from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_advance_prep_round_trip_and_group_removal() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        unit = next(item for item in client.get('/api/reference/units').json() if item['code'] == 'each')
        ingredient = client.post('/api/ingredients', json={
            'name': f'Advance Prep Ingredient {suffix}',
            'shopping_category_id': None,
            'preferred_unit_id': unit['id'],
            'default_location_id': None,
            'perishable': False,
            'notes': None,
            'aliases': [],
        }).json()

        created = client.post('/api/recipes', json={
            'name': f'Advance Prep Recipe {suffix}',
            'description': None,
            'base_servings': '4',
            'serving_unit': 'servings',
            'yield_quantity': None,
            'yield_unit_id': None,
            'prep_time_minutes': 10,
            'cook_time_minutes': 20,
            'notes': None,
            'favorite': False,
            'meal_types': ['DINNER'],
            'tag_ids': [],
            'prep_groups': [
                {'client_key': 'sauce', 'name': 'Sauce', 'sort_order': 0},
                {'client_key': 'veg', 'name': 'Vegetables', 'sort_order': 1},
            ],
            'advance_prep': [
                {
                    'title': 'Marinate sauce base',
                    'lead_time_minutes': 1440,
                    'duration_minutes': 15,
                    'instructions': 'Mix and refrigerate overnight.',
                    'prep_group_key': 'sauce',
                    'sort_order': 0,
                },
                {
                    'title': 'Wash vegetables',
                    'lead_time_minutes': 120,
                    'duration_minutes': None,
                    'instructions': None,
                    'prep_group_key': 'veg',
                    'sort_order': 1,
                },
            ],
            'ingredients': [{
                'ingredient_id': ingredient['id'],
                'prep_group_key': 'veg',
                'quantity': '1',
                'unit_id': unit['id'],
                'display_text': None,
                'preparation': None,
                'prep_method': 'wash',
                'prep_size': None,
                'prep_state': None,
                'optional': False,
                'scaling_mode': 'LINEAR',
                'required_state': 'ANY',
                'sort_order': 0,
                'notes': None,
            }],
        })
        assert created.status_code == 201
        recipe = created.json()
        assert [item['title'] for item in recipe['advance_prep']] == ['Marinate sauce base', 'Wash vegetables']
        groups = {item['name']: item['id'] for item in recipe['prep_groups']}
        assert recipe['advance_prep'][0]['prep_group_id'] == groups['Sauce']
        assert recipe['advance_prep'][1]['prep_group_id'] == groups['Vegetables']
        assert recipe['advance_prep'][0]['lead_time_minutes'] == 1440
        assert recipe['advance_prep'][0]['duration_minutes'] == 15

        updated = client.put(f"/api/recipes/{recipe['id']}", json={
            'name': recipe['name'],
            'description': None,
            'base_servings': '4',
            'serving_unit': 'servings',
            'yield_quantity': None,
            'yield_unit_id': None,
            'prep_time_minutes': 10,
            'cook_time_minutes': 20,
            'notes': None,
            'favorite': False,
            'meal_types': ['DINNER'],
            'tag_ids': [],
            'prep_groups': [{'client_key': 'veg', 'name': 'Vegetables', 'sort_order': 0}],
            'advance_prep': [
                {
                    'title': 'Marinate sauce base',
                    'lead_time_minutes': 1440,
                    'duration_minutes': 15,
                    'instructions': 'Mix and refrigerate overnight.',
                    'prep_group_key': None,
                    'sort_order': 0,
                },
                {
                    'title': 'Wash vegetables',
                    'lead_time_minutes': 120,
                    'duration_minutes': 5,
                    'instructions': 'Rinse thoroughly.',
                    'prep_group_key': 'veg',
                    'sort_order': 1,
                },
            ],
            'ingredients': [{
                'ingredient_id': ingredient['id'],
                'prep_group_key': 'veg',
                'quantity': '1',
                'unit_id': unit['id'],
                'display_text': None,
                'preparation': None,
                'prep_method': 'wash',
                'prep_size': None,
                'prep_state': None,
                'optional': False,
                'scaling_mode': 'LINEAR',
                'required_state': 'ANY',
                'sort_order': 0,
                'notes': None,
            }],
            'active': True,
        })
        assert updated.status_code == 200
        result = updated.json()
        assert len(result['advance_prep']) == 2
        assert result['advance_prep'][0]['prep_group_id'] is None
        assert result['advance_prep'][1]['prep_group_id'] == result['prep_groups'][0]['id']
        assert result['advance_prep'][1]['duration_minutes'] == 5
        assert result['advance_prep'][1]['instructions'] == 'Rinse thoroughly.'

        scaled = client.post(f"/api/recipes/{recipe['id']}/scale", json={'requested_servings': '8', 'unit_overrides': {}})
        assert scaled.status_code == 200
        assert scaled.json()['ingredients'][0]['quantity'] == '2.000000'


def test_legacy_recipe_without_advance_prep_still_works() -> None:
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        created = client.post('/api/recipes', json={
            'name': f'Legacy Advance Prep {suffix}',
            'description': None,
            'base_servings': '4',
            'serving_unit': 'servings',
            'yield_quantity': None,
            'yield_unit_id': None,
            'prep_time_minutes': 0,
            'cook_time_minutes': 0,
            'notes': None,
            'favorite': False,
            'meal_types': [],
            'tag_ids': [],
            'prep_groups': [],
            'ingredients': [],
        })
        assert created.status_code == 201
        assert created.json()['advance_prep'] == []
