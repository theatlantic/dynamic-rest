from rest_framework import fields
from django.db.models.related import RelatedObject
from django.db.models import ManyToManyField
import importlib


class DynamicField(fields.Field):

  """
  Generic field to capture additional custom field attributes
  """

  def __init__(self, deferred=False, **kwargs):
    """
    Arguments:
      deferred: Whether or not this field is deferred,
        i.e. not included in the response unless specifically requested.
    """
    super(DynamicField, self).__init__(**kwargs)
    self.deferred = deferred


class DynamicRelationField(DynamicField):

  """Proxy for a sub-serializer.

  Supports passing in the target serializer as a class or string,
  resolves after binding to the parent serializer.
  """

  SERIALIZER_KWARGS = set(('many', 'source'))

  def __init__(self, serializer_class, many=False, **kwargs):
    """
    Arguments:
      serializer_class: Serializer class (or string representation) to proxy.
    """
    self.kwargs = kwargs
    self._serializer_class = serializer_class
    if '.' in self.kwargs.get('source', ''):
      raise Exception('Nested relationships are not supported')
    super(DynamicRelationField, self).__init__(**kwargs)
    self.kwargs['many'] = many

  def bind(self, *args, **kwargs):
    super(DynamicRelationField, self).bind(*args, **kwargs)
    parent_model = self.parent.Meta.model
    model_field = parent_model._meta.get_field_by_name(self.source)[0]
    remote = isinstance(model_field, (ManyToManyField, RelatedObject))
    if not 'required' in self.kwargs and \
      (remote or model_field.has_default() or model_field.null):
      self.required = False
    if not 'allow_null' in self.kwargs and getattr(model_field, 'null', False):
      self.allow_null = True

  @property
  def serializer(self):
    if hasattr(self, '_serializer'):
      return self._serializer

    serializer = self.serializer_class(
        **{k: v for k, v in self.kwargs.iteritems() if k in self.SERIALIZER_KWARGS})
    self._serializer = serializer
    return serializer

  def get_attribute(self, instance):
    return instance

  def to_representation(self, instance):
    serializer = self.serializer
    source = self.source
    if not self.kwargs['many'] and serializer.id_only():
      # attempt to optimize by reading the related ID directly
      # from the current instance rather than from the related object
      source_id = '%s_id' % source
      if hasattr(instance, source_id):
        return getattr(instance, source_id)
    try:
      related = getattr(instance, source)
    except:
      return None
    return serializer.to_representation(related)

  @property
  def serializer_class(self):
    serializer_class = self._serializer_class
    if not isinstance(serializer_class, basestring):
      return serializer_class

    parts = serializer_class.split('.')
    module_path = '.'.join(parts[:-1])
    if not module_path:
      if getattr(self, 'parent', None) is None:
        raise Exception(
            "Can not load serializer '%s' before binding or without specifying full path" % serializer_class)

      # try the module of the parent class
      module_path = self.parent.__module__

    module = importlib.import_module(module_path)
    serializer_class = getattr(module, parts[-1])

    self._serializer_class = serializer_class
    return serializer_class

  def __getattr__(self, name):
    """Proxy all methods and properties on the underlying serializer."""
    return getattr(self.serializer, name)