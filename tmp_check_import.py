import tablegis
print('module file:', getattr(tablegis, '__file__', None))
print('has add_polygon:', hasattr(tablegis, 'add_polygon'))
print('available:', [a for a in dir(tablegis) if 'polygon' in a.lower()])
