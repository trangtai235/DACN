from .common import *
@api
@require_GET
def queue(request):
    project=project_for(request,request.GET['project'])
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt kiểm tra mù trước khi xem gợi ý lượt đầu.')
    qs=Comment.objects.filter(project=project,first_frozen_at__isnull=True,ai_label__in=['TOXIC','NON_TOXIC']).order_by('id')
    row=qs.first()
    if row:AIExposure.objects.get_or_create(comment=row,user=request.user)
    return JsonResponse({'comment':serialize_comment(row) if row else None,'remaining':qs.count()})
