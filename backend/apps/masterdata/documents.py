"""
Elasticsearch document definitions for master data
"""
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from .models import Item, Customer, Supplier


@registry.register_document
class ItemDocument(Document):
    """Elasticsearch document for Item model"""
    
    category = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
        'code': fields.TextField(),
    })
    
    class Index:
        name = 'items'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }
    
    class Django:
        model = Item
        fields = [
            'sku',
            'name',
            'specification',
            'barcode',
            'standard_cost',
            'min_stock',
            'max_stock',
            'is_active',
        ]
        related_models = ['category']
    
    def get_queryset(self):
        """Return queryset for indexing"""
        return super().get_queryset().select_related('category')
    
    def get_instances_from_related(self, related_instance):
        """If category is updated, update all related items"""
        if isinstance(related_instance, type(self.Django.model.category.field.related_model)):
            return related_instance.items.all()


@registry.register_document
class CustomerDocument(Document):
    """Elasticsearch document for Customer model"""
    
    class Index:
        name = 'customers'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }
    
    class Django:
        model = Customer
        fields = [
            'code',
            'name',
            'contact_person',
            'phone',
            'email',
            'address',
            'credit_limit',
            'status',
        ]


@registry.register_document
class SupplierDocument(Document):
    """Elasticsearch document for Supplier model"""
    
    class Index:
        name = 'suppliers'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }
    
    class Django:
        model = Supplier
        fields = [
            'code',
            'name',
            'contact_person',
            'phone',
            'email',
            'address',
            'payment_terms',
            'status',
        ]

