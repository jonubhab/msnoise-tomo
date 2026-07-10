import os
from msnoise.api import *
from sqlalchemy import text

def main(all,comp):
    db = connect()
    result = db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
    db.commit()
    deleted=0
    if comp:
        params = get_params(db)
        comps = params.components_to_compute
        filters = get_filters(db)
        while is_next_job(db, jobtype='TOMO_FTAN'):
            jobs = get_next_job(db, jobtype='TOMO_FTAN')

            for job in jobs:
                netsta1, netsta2 = job.pair.split(':')
                for filter in filters:
                    fn = os.path.join("DISP CURVE PLOTS", "%02i" % filter.ref, comp,
                                      "%s - %s.png" % (netsta1, netsta2))
                    if os.path.exists(fn):
                        os.remove(fn)
                        deleted += 1
        result = db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
        db.commit()
    if all:
        params = get_params(db)
        comps = params.components_to_compute
        filters = get_filters(db)
        while is_next_job(db, jobtype='TOMO_FTAN'):
            jobs = get_next_job(db, jobtype='TOMO_FTAN')

            for job in jobs:
                netsta1, netsta2 = job.pair.split(':')
                for filter in filters:
                    for comp in comps:
                        fn = os.path.join("DISP CURVE PLOTS", "%02i" % filter.ref, comp,
                                          "%s - %s.png" % (netsta1, netsta2))
                        if os.path.exists(fn):
                            os.remove(fn)
                            deleted+=1
        result = db.execute(text("UPDATE jobs SET flag='T' WHERE jobtype='TOMO_FTAN'"))
        db.commit()
    print(f"{result.rowcount} jobs reset to T")
    print(f"{deleted} picks deleted.")

if __name__ == "__main__":
    main()
