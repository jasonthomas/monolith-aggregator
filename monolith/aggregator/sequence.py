from ConfigParser import NoOptionError
from collections import defaultdict

from monolith.aggregator.resolver import resolve_name
from monolith.aggregator import logger


class Sequence(object):
    def __init__(self, config, sequence=None):
        self.parser = config

        # parsing the sequence, phases, sources and targets
        if sequence is None:
            try:
                sequence = config.get('monolith', 'sequence')
            except NoOptionError:
                raise ValueError("You need to define a sequence.")

        sequence = [phase.strip() for phase in sequence.split(',')]
        self.config = defaultdict(dict)
        keys = ('phase', 'source', 'target')

        for section in config.sections():
            for key in keys:
                prefix = key + ':'
                if section.startswith(prefix):
                    name = section[len(prefix):]
                    self.config[key][name] = dict(config.items(section))

        self.plugins = {}

        # a sequence is made of phases
        self._sequence = [self._build_phase(phase) for phase in sequence]

    def __iter__(self):
        return self._sequence.__iter__()

    def _load(self, name, type_):
        name = name.strip()
        if name not in self.config[type_]:
            raise ValueError('%r %s is undefined' % (name, type_))
        return self._load_plugin(type_, name, self.config[type_][name])

    def _build_phase(self, phase):
        if phase not in self.config['phase']:
            raise ValueError('%r phase is undefined' % phase)

        options = self.config['phase'][phase]
        targets = [self._load(target, 'target')
                   for target in options['targets'].split(',')]
        sources = [self._load(source, 'source')
                   for source in options['sources'].split(',')]
        return phase, sources, targets

    def _load_plugin(self, type_, name, options):
        logger.debug('Loading %s:%s' % (type_, name))
        source_id = type_, options['id']

        if source_id in self.plugins:
            return self.plugins[source_id]

        options = dict(options)
        try:
            plugin = resolve_name(options['use'])
        except KeyError:
            msg = "Missing the 'use' option for plugin %r" % name
            msg += '\nGot: %s' % str(options)
            raise KeyError(msg)

        options['parser'] = self.parser
        options['id'] = ':'.join(source_id)
        del options['use']
        instance = plugin(**options)
        self.plugins[source_id] = instance
        return instance
