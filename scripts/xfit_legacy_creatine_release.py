"""Exact source-reviewed creatine scopes. Reuse tested legacy publisher."""
import sys
from scripts.xfit_legacy_mat_release import Scope, snapshot, apply
from scripts.wp_publish import PublishError
SCOPES = {
    "11753": Scope(11753, "kreatin-pro-zacatecniky-jaky-druh-kreatinu-si-vybrat-pro-cviceni", "3fae0a8f402b6daeb8048e2208b9256ca2acaab5bea834d2e7fa13da40454e8c", "2026-11-04T09:16:22", "content/revisions/legacy-creatine-11753.json", lane="creatine"),
    "11863": Scope(11863, "porovnani-nejucinnejsich-druhu-kreatinu-pro-sportovce", "bd4cce259e0bc7cb68e273514fd85075a4e1cc52a7773485d64b6dd2357360e6", "2026-11-01T18:58:18", "content/revisions/legacy-creatine-11863.json", lane="creatine"),
    "11882": Scope(11882, "nejlepsi-kreatin-pro-fitness-jak-vybrat-ten-spravny-pro-vas", "49a2db2e825fab38f4067a59a666ce858c86b86d84bdade749df97b2dca19fb9", "2026-11-01T09:17:50", "content/revisions/legacy-creatine-11882.json", lane="creatine"),
}
if __name__=="__main__":
    try:
        if len(sys.argv)!=3 or sys.argv[1] not in SCOPES or sys.argv[2] not in {"snapshot","apply"}:
            raise PublishError("Unknown pinned revision")
        (snapshot if sys.argv[2]=="snapshot" else apply)(SCOPES[sys.argv[1]])
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_LEGACY_CREATINE_REVISION_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
