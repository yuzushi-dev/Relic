"""Hermes-native Gumi plugin (PR22E/F/H).

Skeleton package: real provider integration is delivered via the Hermes plugin
host. Every public surface here defaults to fail-closed behavior so the plugin
never silently injects context, even on partial config.
"""

from relic.gumi_plugin.plugin import GumiPlugin, load_plugin
from relic.gumi_plugin.admission import AdmissionPolicy, AdmissionVerdict
from relic.gumi_plugin.continuity import ContinuityCompactor
from relic.gumi_plugin.storage import GumiStorage
from relic.gumi_plugin.critic import OutputCritic, CriticVerdict
from relic.gumi_plugin.cron_tasks import CronJob, list_cron_jobs

__all__ = [
    "GumiPlugin",
    "load_plugin",
    "AdmissionPolicy",
    "AdmissionVerdict",
    "ContinuityCompactor",
    "GumiStorage",
    "OutputCritic",
    "CriticVerdict",
    "CronJob",
    "list_cron_jobs",
]
