"""Web application phục vụ release artifact của dự án causal uplift.

App chỉ đọc artifact đã freeze trong ``output/``. Nó không train model khi nhận
request; endpoint duy nhất chạy model là ``/api/score``, và nó dùng scorer đã fit
sẵn được lưu xuống đĩa.
"""

__all__ = ["service", "api"]
