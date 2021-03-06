import logging
from followthemoney import model
from followthemoney.types import registry

from aleph.core import es, db
from aleph.model import Entity
from aleph.index import entities as index
from aleph.index.core import entities_index
from aleph.index.util import authz_query, field_filter_query
from aleph.logic.notifications import flush_notifications
from aleph.logic.entities.bulk import bulk_load, bulk_load_query  # noqa

log = logging.getLogger(__name__)
BULK_PAGE = 500


def update_entity(entity):
    log.info("Update [%s]: %s", entity.id, entity.name)
    return index.index_entity(entity)


def update_entities():
    q = db.session.query(Entity)
    for entity in q:
        update_entity(entity)


def delete_entity(entity, deleted_at=None):
    flush_notifications(entity)
    entity.delete(deleted_at=deleted_at)
    index.delete_entity(entity.id)


def entity_references(entity, authz):
    """Given a particular entity, find all the references to it from other
    entities, grouped by the property where they are used."""
    schema = model[entity.get('schema')]

    # Generate all the possible mention locations.
    properties = []
    queries = []
    for prop in model.properties:
        if prop.type != registry.entity:
            continue
        if not schema.is_a(prop.range):
            continue

        field = 'properties.%s' % prop.name
        queries.append({})
        queries.append({
            'size': 0,
            'query': {
                'bool': {
                    'filter': [
                        authz_query(authz),
                        {'term': {'schemata': prop.schema.name}},
                        {'term': {field: entity.get('id')}},
                    ]
                }
            }
        })
        properties.append(prop)

    if not len(queries):
        return

    # Run a count search (with schema facet?)
    res = es.msearch(index=entities_index(), body=queries)
    for prop, resp in zip(properties, res.get('responses', [])):
        total = resp.get('hits', {}).get('total')
        if total is not None and total > 0:
            yield (prop, total)


def entity_tags(entity, authz):
    """Do a search on tags of an entity."""
    # NOTE: This must also work for documents.
    FIELDS = [
        'names',
        'emails',
        'phones',
        'addresses',
        'identifiers'
    ]
    pivots = []
    queries = []
    # Go through all the tags which apply to this entity, and find how
    # often they've been mentioned in other entities.
    for field in FIELDS:
        for value in entity.get(field, []):
            if value is None or not len(value):
                continue
            queries.append({})
            queries.append({
                'size': 0,
                'query': {
                    'bool': {
                        'filter': [
                            authz_query(authz),
                            field_filter_query(field, value)
                        ],
                        'must_not': [
                            {'ids': {'values': [entity.get('id')]}},
                        ]
                    }
                }
            })
            pivots.append((field, value))

    if not len(queries):
        return

    res = es.msearch(index=entities_index(), body=queries)
    for (field, value), resp in zip(pivots, res.get('responses', [])):
        total = resp.get('hits', {}).get('total')
        if total is not None and total > 0:
            yield (field, value, total)
