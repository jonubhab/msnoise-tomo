class Cache:

    _cache=[None]
    _i=0

    @staticmethod
    def update(ele):
        if ele != Cache.current:
            if not Cache._cache[Cache._i]:
                Cache._cache[Cache._i]=ele
            else:
                Cache._i+=1
                if Cache._i==len(Cache._cache): Cache._cache.append(None)
                Cache._cache[Cache._i]=ele
            Cache._cache=Cache._cache[:Cache._i+1]

    @staticmethod
    def undo():
        if Cache._i>0:
            Cache._i-=1
            return Cache._cache[Cache._i]
        return None

    @staticmethod
    def redo():
        if Cache._i<len(Cache._cache)-1:
            Cache._i+=1
            return Cache._cache[Cache._i]
        return None

    @staticmethod
    def refresh():
        Cache._cache=[None]
        Cache._i=0


    @classmethod
    @property
    def current(cls):
        return cls._cache[Cache._i]