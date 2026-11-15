from django.urls import path
from .api import projects,annotations,versions,integrations,sources,accounts,research,automatic
from .api import collaboration as paired
from .api import budget
urlpatterns=[path('research-queue',research.queue),
 path('budget',budget.overview),path('budget/runs/<int:run_id>/control',budget.control),
 path('budget/tasks/<int:task_id>/clock',budget.clock),path('budget/runs/<int:run_id>/report',budget.evaluation),
 path('collaboration',paired.dashboard),path('collaboration/start',paired.start),path('collaboration/runs/<int:run_id>',paired.pairs),
 path('collaboration/report',paired.experiment_report),
 path('collaboration/runs/<int:run_id>/retry',paired.retry),
 path('collaboration/pairs/<int:pair_id>',paired.detail),path('collaboration/pairs/<int:pair_id>/expose',paired.expose),
 path('collaboration/pairs/<int:pair_id>/clock',paired.decision_clock),
 path('collaboration/pairs/<int:pair_id>/decision',paired.save),path('collaboration/pairs/<int:pair_id>/adjudicate',paired.adjudicate),
 path('collaboration/decisions/<int:decision_id>/approve',paired.approve),path('collaboration/partition',paired.partition),
 path('collaboration/dataset',paired.dataset),path('collaboration/train',paired.training),path('collaboration/activate',paired.activate),
 path('auto-label/runs',automatic.runs),path('auto-label/start',automatic.start),path('auto-label/runs/<int:run_id>',automatic.detail),path('auto-label/runs/<int:run_id>/control',automatic.control),
 path('project-settings',projects.settings_view),path('labels',projects.label_settings),path('members',projects.member_settings),path('invite',projects.invite),path('accept-invite',projects.accept_invite),
 path('comments',annotations.comments),path('workspace',annotations.workspace),path('comments/<int:comment_id>/annotation',annotations.submit),path('comments/<int:comment_id>/undo',annotations.undo),path('comments/<int:comment_id>/gold',annotations.adjudicate),path('quality',annotations.quality_view),
 path('versions',versions.version_create),path('versions/<int:version_id>',versions.version_download),path('versions/<int:version_id>/restore',versions.version_restore),path('export',versions.export_dataset),path('exports',versions.export_history),
 path('connections',integrations.connections),path('connections/save',integrations.connection_save),path('connections/test',integrations.connection_test),path('connections/delete',integrations.connection_delete),path('connections/configuration',integrations.configuration),path('selection',integrations.select_model),
 path('import-csv',sources.import_csv),path('sources/<int:source_id>/action',sources.source_action),path('jobs',sources.jobs),path('jobs/<int:job_id>/action',sources.job_action),
 path('profile',accounts.profile),path('profile/save',accounts.profile_save),path('verify/send',accounts.verification_send),path('verify',accounts.verification_accept),path('password/request',accounts.password_request),path('password/reset',accounts.password_reset)
]
