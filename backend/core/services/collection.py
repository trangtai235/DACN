def collection_limit(value):
    """An omitted/blank limit collects until the API has no further pages."""
    if value is None or value == '' or isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, bool) or not str(value).strip().isdecimal() or int(value) < 1:
        raise ValueError('Số bình luận tối đa phải là số nguyên dương hoặc để trống để lấy tất cả.')
    return int(value)
