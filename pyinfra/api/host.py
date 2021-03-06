from __future__ import unicode_literals

import click

from pyinfra import logger

from .connectors import EXECUTION_CONNECTORS
from .exceptions import ConnectError, PyinfraError
from .facts import (
    create_host_fact,
    delete_host_fact,
    get_fact_names,
    get_host_fact,
    is_fact,
)


class HostFacts(object):
    def __init__(self, host=None):
        self.host = host

    def __dir__(self):
        return get_fact_names()

    def _check_host(self):
        if not self.host:
            raise TypeError('Cannot call this function with no host!')

    def __getattr__(self, key):
        self._check_host()

        if not is_fact(key):
            raise AttributeError('No such fact: {0}'.format(key))

        # Ensure this host is connected
        connection = self.host.connect(for_fact=key)

        # If we can't connect - fail immediately as we specifically need this
        # fact for this host and without it we cannot satisfy the deploy.
        if not connection:
            raise PyinfraError('Could not connect to {0} for fact {1}!'.format(
                self.host, key,
            ))

        return get_host_fact(self.host.state, self.host, key)

    def _create(self, key, data=None, args=None):
        self._check_host()
        return create_host_fact(self.host.state, self.host, key, data, args)

    def _delete(self, key, args=None):
        self._check_host()
        return delete_host_fact(self.host.state, self.host, key, args)


class Host(object):
    '''
    Represents a target host. Thin class that links up to facts and host/group
    data.
    '''

    connection = None
    state = None
    fact = HostFacts()  # this isn't usable, but provides support for dir()

    def __init__(
        self, name, inventory, groups, data,
        executor=EXECUTION_CONNECTORS['ssh'],
    ):
        self.inventory = inventory
        self.groups = groups
        self.data = data
        self.executor = executor
        self.name = name

        # Attach the fact proxy
        self.fact = HostFacts(self)

        # Arbitrary dict for connector use
        self.connector_data = {}

    def __repr__(self):
        return self.name

    @property
    def host_data(self):
        return self.inventory.get_host_data(self.name)

    @property
    def group_data(self):
        return self.inventory.get_groups_data(self.groups)

    @property
    def print_prefix(self):
        return '{0}[{1}] '.format(
            click.style(''),  # reset
            click.style(self.name, bold=True),
        )

    def style_print_prefix(self, *args, **kwargs):
        return '{0}[{1}] '.format(
            click.style(''),  # reset
            click.style(self.name, *args, **kwargs),
        )

    def _check_state(self):
        if not self.state:
            raise TypeError('Cannot call this function with no state!')

    # Connector proxy
    #

    def connect(self, for_fact=None, show_errors=True):
        self._check_state()
        if not self.connection:
            try:
                self.connection = self.executor.connect(self.state, self)
            except ConnectError as e:
                if show_errors:
                    log_message = '{0}{1}'.format(
                        self.print_prefix,
                        click.style(e.args[0], 'red'),
                    )
                    logger.error(log_message)
            else:
                log_message = '{0}{1}'.format(
                    self.print_prefix,
                    click.style('Connected', 'green'),
                )
                if for_fact:
                    log_message = '{0}{1}'.format(
                        log_message,
                        ' (for {0} fact)'.format(for_fact),
                    )

                logger.info(log_message)

        return self.connection

    def disconnect(self):
        self._check_state()
        # Disconnect is an optional function for executors if needed
        disconnect_func = getattr(self.executor, 'disconnect', None)
        if disconnect_func:
            return disconnect_func(self.state, self)

    def run_shell_command(self, *args, **kwargs):
        self._check_state()
        return self.executor.run_shell_command(self.state, self, *args, **kwargs)

    def put_file(self, *args, **kwargs):
        self._check_state()
        return self.executor.put_file(self.state, self, *args, **kwargs)

    def get_file(self, *args, **kwargs):
        self._check_state()
        return self.executor.get_file(self.state, self, *args, **kwargs)
