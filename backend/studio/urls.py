from django.urls import path
from .api import projects,annotations,versions,integrations,sources,accounts,research
urlpatterns=[path('research-queue',research.queue),
 path('project-settings',projects.settings_view),path('labels',projects.label_settings),path('members',projects.member_settings),path('invite',projects.invite),path('accept-invite',projects.accept_invite),
 path('comments',annotations.comments),path('workspace',annotations.workspace),path('comments/<int:comment_id>/annotation',annotations.submit),path('comments/<int:comment_id>/undo',annotations.undo),path('comments/<int:comment_id>/gold',annotations.adjudicate),path('quality',annotations.quality_view),
 path('versions',versions.version_create),path('versions/<int:version_id>',versions.version_download),path('versions/<int:version_id>/restore',versions.version_restore),path('export',versions.export_dataset),path('exports',versions.export_history),
 path('connections',integrations.connections),path('connections/save',integrations.connection_save),path('connections/test',integrations.connection_test),path('selection',integrations.select_model),
 path('import-csv',sources.import_csv),path('sources/<int:source_id>/action',sources.source_action),path('jobs',sources.jobs),path('jobs/<int:job_id>/action',sources.job_action),
 path('profile',accounts.profile),path('profile/save',accounts.profile_save),path('verify/send',accounts.verification_send),path('verify',accounts.verification_accept),path('password/request',accounts.password_request),path('password/reset',accounts.password_reset)
]
