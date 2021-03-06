from entityextractor.aggregate import EntityAggregator
from entityextractor.result import PersonResult


class TestAggregate(object):

    def test_aggregator(self):
        agg = EntityAggregator()
        agg.add(PersonResult(agg, 'Banana', 0, 12))
        assert len(agg) == 0, agg
        agg.add(PersonResult(agg, 'Mr. Max Banana', 0, 12))
        assert len(agg) == 1, agg
        agg.add(PersonResult(agg, 'Max Banana', 0, 12))
        assert len(agg) == 1, agg

    def test_entities(self):
        agg = EntityAggregator()
        agg.add(PersonResult(agg, 'Mr. Max Banana', 0, 12))
        agg.add(PersonResult(agg, 'Mr. Max Banana', 0, 12))
        agg.add(PersonResult(agg, 'max Banana', 0, 12))
        for label, category, weight in agg.entities:
            assert label == 'Max Banana', label
            # assert category == 'baa', label
            assert weight == 3, weight

    def test_merkel(self):
        agg = EntityAggregator()
        agg.extract('Das ist der Pudel von Angela Merkel', ['de', 'en'])
        entities = [l for l, c, w in agg.entities]
        assert 'Angela Merkel' in entities, entities

    def test_multi(self):
        agg = EntityAggregator()
        text = "This is a text about Foo Blubb, a leader in " \
               "this industry. The should not be confused with Foo Blubb, " \
               "a smaller firm."
        agg.extract(text, ['en'])
        entities = [l for l, c, w in agg.entities]
        assert 'Foo Blubb' in entities, entities

    # def test_select_label(self):
    #     labels = ['Mr Blue', 'Mr BLUE', 'Mr Blu', 'Mr. Blue']
    #     assert select_label(labels) == 'Mr Blue'

    def test_phonenumber(self):
        agg = EntityAggregator()
        text = "Mr. Flubby Flubber called the number tel:+919988111222 twice"
        agg.extract(text, ['en'])
        entities = [l for l, c, w in agg.entities]
        assert '+919988111222' in entities
        assert 'in' in entities

    def test_country(self):
        agg = EntityAggregator()
        text = """This is a document about the United States. But also about
        Syria and Germany.
        """
        agg.extract(text, ['en'])
        assert 'us' in agg.countries
        # fails
        assert 'de' in agg.countries
        assert 'sy' in agg.countries
