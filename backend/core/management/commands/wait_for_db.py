import time
from django.core.management.base import BaseCommand,CommandError
from django.db import connection
class Command(BaseCommand):
    def handle(self,*a,**kw):
        for i in range(45):
            try:
                connection.ensure_connection()
                with connection.cursor() as c:c.execute('SHOW server_version_num');version=int(c.fetchone()[0])
                if not 150000<=version<190000:raise CommandError('Bản dựng này yêu cầu PostgreSQL 15–18; kiểm tra DB_HOST.')
                self.stdout.write(f'PostgreSQL {version // 10000} sẵn sàng.');return
            except CommandError:raise
            except Exception:
                connection.close();time.sleep(1)
        raise CommandError('Không kết nối được PostgreSQL sau 45 giây; kiểm tra .env và trạng thái DB.')
