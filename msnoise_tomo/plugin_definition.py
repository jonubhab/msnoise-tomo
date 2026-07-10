import click
from flask_admin import expose
from flask_admin.contrib.sqla import ModelView
from wtforms.fields import StringField, SelectField
import markdown
from flask import Flask, redirect, request, render_template
from flask import Markup

from .tomo_table_def import TomoConfig


''''''
import os
if os.path.exists("ignore_pairs.txt"):
    import msnoise.api as msapi
    _original_get_next_job = msapi.get_next_job
    _original_get_station_pairs = msapi.get_station_pairs

    def get_ignored_pairs():
        """Reads pairs to ignore from ignore_pairs.txt in the root directory."""
        ignored = set()
        filename = "ignore_pairs.txt"
        if os.path.exists(filename):
            with open(filename, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):  # Allows commenting out lines with '#'
                        ignored.add(line)
        return ignored

    def patched_get_next_job(*args, **kwargs):
        jobs = _original_get_next_job(*args, **kwargs)
        if kwargs.get('jobtype') == 'TOMO_FTAN' and jobs:
            ignored_pairs = get_ignored_pairs()
            if ignored_pairs:
                return [job for job in jobs if job.pair not in ignored_pairs]

        return jobs

    def patched_get_station_pairs(*args, **kwargs):
        station_pairs = _original_get_station_pairs(*args, **kwargs)
        ignored_pairs = get_ignored_pairs()
        if len(ignored_pairs)>0:
            for sta1,sta2 in station_pairs:
                # Check both directions (A, B) and (B, A) just in case
                if "%s.%s:%s.%s"%(sta1.net,sta1.sta,sta2.net,sta2.sta) not in ignored_pairs and "%s.%s:%s.%s"%(sta2.net,sta2.sta,sta1.net,sta1.sta) not in ignored_pairs:
                    yield sta1,sta2
        else:
            yield from station_pairs


    msapi.get_next_job = patched_get_next_job
    msapi.get_station_pairs = patched_get_station_pairs
''''''


### COMMAND LINE INTERFACE PLUGIN DEFINITION

@click.group()
def tomo():
    """Package to compute dispersion curves using automated FTAN and
    invert them to obtain a velocity model at different periods."""
    pass

@click.command()
def info():
    from msnoise.api import connect, get_config
    from .default import default
    db = connect()
    click.echo('')
    click.echo('Raw config bits: "D"efault or "M"odified (green)')
    for key in default.keys():
        tmp = get_config(db, key, plugin='Tomo')
        if tmp == default[key][1]:
            click.secho(" D %s: %s" %(key, tmp ))
        else:
            click.secho(" M %s: %s" %(key, tmp ), fg='green')

@click.command()
def install():
    from .install import main
    main()


@click.command(name="prepare_ccf")
def prepare_ccf():
    from .export_single_sided import main
    main()

@click.command(name="rotate_ref")
def rotate_ref():
    from .rotate_ref import main
    main()

@click.command(name="ftan_sw")
def ftan_sw():
    from .ftan_sw import main
    main()

@click.command(name="ftan_example")
def ftan_example():
    from .examplepickdispcurve import main
    main()

@click.option('-p', '--pair', default=None,  help='FTAN a specific pair\tFormat: NET.STA1_NET.STA2',
              multiple=True)
@click.option('-b', '--bmin', default=None,  help='force bmin',)
@click.option('-B', '--bmax', default=None,  help='force bmax',)
@click.option('-s', '--show', default=1,  help='show plot',)
@click.option('-i','--interact',default=False, help='Verify and pick interactively',is_flag=True)
@click.command()
def ftan(pair, bmin, bmax, show,interact):
    from .ftan import main
    main(pair, bmin, bmax, show,interact)

@click.option('-p', '--pair', default=None,  help='FTAN a specific pair\tFormat: NET.STA1_NET.STA2',
              multiple=True)
@click.option('-s', '--show', default=False,  help='show plot',is_flag=True)
@click.option('-i','--interact',default=False, help='Verify and pick interactively',is_flag=True)
@click.command(name="autopick_sw")
def autopick_sw(pair,show,interact):
    from .autopick_sw import main
    main(pair,show,interact)

@click.option('-a','--all',is_flag=True, default=False,help='Reset the entire FTAN process and start from scratch.')
@click.option('-c', '--comp', default=None, help='Component to be deleted entirely')
@click.command(name="reset_ftan")
def reset_ftan(all,comp):
    if all:
        confirm_text = click.prompt(
            "This will reset ALL FTAN jobs and progress. Type 'DELETE PROGRESS' to continue"
        )
        if confirm_text.strip() != "DELETE PROGRESS":
            click.echo("Aborted.")
            return
    elif comp:
        confirm_text = click.prompt(
            "This will reset ALL FTAN jobs and progress for %s. Type 'DELETE PROGRESS' to continue"%(comp)
        )
        if confirm_text.strip() != "DELETE PROGRESS":
            click.echo("Aborted.")
            return
    from .reset_ftan import main
    main(all,comp)

@click.option('-i','--interact',default=False, help='Verify and pick interactively',is_flag=True)
@click.command()
def iftan(interact):
    from .iftan import main
    main(interact)

@click.option('-vmin', '--vmin', default=0.0, help='Minimum Group Velocity Filter')
@click.option('-vmax', '--vmax', default=float('inf'), help='Maximum Group Velocity Filter')
@click.command(name="prepare_tomo")
def prepare_tomo(vmin,vmax):
    from .prepare_tomo import main
    main(vmin,vmax)

@click.option('-s', '--show', default=False,  help='show plot',is_flag=True)
#@click.option('-c', '--comp', default=None, help='Components (ZZ, ZR,...)',nargs=-1)
@click.argument('comp', nargs=-1)
@click.command(name="plot_disp")
def plot_disp(comp,show):
    from .plot_disp import main
    '''
    if comp:
        comp=list(comp)
        if "-s" in comp or "--show" in comp:
            comp.remove("-s")
            comp.remove("--show")
            show=True
            '''
    comp = list(comp) if comp else None
    main(comp,show)

@click.option('-p', '--per',type=float, default=None,  help='force per',)
@click.option('--a1', type=float, default=None, help='force bmin',)
@click.option('--b1', type=float, default=None, help='force bmin',)
@click.option('--l1', type=float, default=None, help='force bmin',)
@click.option('--s1', type=float, default=None, help='force bmin',)
@click.option('--a2', type=float, default=None, help='force bmin',)
@click.option('--b2', type=float, default=None, help='force bmin',)
@click.option('--l2', type=float, default=None, help='force bmin',)
@click.option('--s2', type=float, default=None, help='force bmin',)
@click.option('-f', '--filterid', default=1, help='Filter ID')
@click.option('-c', '--comp', default="ZZ", help='Components (ZZ, ZR,...)')
@click.option('-s', '--show', help='Show interactively?',
              default=True, type=bool)
@click.command()
def answt(per, a1, b1, l1, s1, a2, b2, l2, s2, filterid, comp, show):
    from .ANSWT import main
    main(per, a1, b1, l1, s1, a2, b2, l2, s2, filterid, comp, show)

@click.option('-p', '--per',type=float, default=None,  help='force per',)

@click.option('-f', '--filterid', default=1, help='Filter ID')
@click.option('-s', '--show', help='Show interactively?',
              default=False, type=bool)
@click.command(name="anisotropy")
def anisotropy(per,filterid,show):
    from .anisotropy import main
    main(per,filterid,show)


@click.command(name="prepare_1d")
def prepare_1d():
    from .prepare_1d import main
    main()


@click.command()
@click.option('-vmin', '--vmin', default=0.0, help='Minimum Group Velocity Filter')
@click.option('-vmax', '--vmax', default=float('inf'), help='Maximum Group Velocity Filter')
@click.option('-f', '--filterid', default=1, help='Filter ID')
@click.option('-c', '--comp', default="ZZ", help='Components (ZZ, ZR,...)')
def plot(filterid, comp,vmin,vmax):
    from .plotdisp import main
    main(filterid, comp,vmin,vmax)

@click.command()
def plot3d():
    from .plot3d import main
    main()

@click.option('-f', '--filterid', default=1, help='Filter ID')
@click.option('-c', '--comp', default="ZZ", help='Components (ZZ, ZR,...)')
@click.option('-vmin', '--vmin', default=None, help='Minimum Group Velocity Filter')
@click.option('-vmax', '--vmax', default=None, help='Maximum Group Velocity Filter')
@click.option('-s', '--show', default=False,  help='show plot',is_flag=True)
@click.command(name="grid_disp")
def grid_disp(filterid, comp,vmin,vmax,show):
    from .grid_disp import main
    main(filterid, comp,float(vmin),float(vmax),show)


tomo.add_command(info)
tomo.add_command(ftan_example)
tomo.add_command(prepare_ccf)
tomo.add_command(rotate_ref)
tomo.add_command(ftan_sw)
tomo.add_command(prepare_tomo)
tomo.add_command(ftan)
tomo.add_command(reset_ftan)
tomo.add_command(autopick_sw)
tomo.add_command(iftan)
tomo.add_command(install)
tomo.add_command(plot_disp)
tomo.add_command(answt)
tomo.add_command(anisotropy)
tomo.add_command(plot)
tomo.add_command(prepare_1d)
tomo.add_command(plot3d)
tomo.add_command(grid_disp)


from .default import default
### WEB INTERFACE PLUGIN DEFINITION
class TomoConfigView(ModelView):
    # Disable model creation
    edit_template = 'admin/model/edit-config.html'
    view_title = "MSNoise TOMO Configuration"
    name = "Configuration"

    #inline_models = (SaraConfig,)
    can_create = False
    can_delete = False
    page_size = 50
    # Override displayed fields
    column_list = ('name', 'value')
    # wont work because sigma1 is the content of the value, not the name of the
    # field itself!!
    # form_overrides = {"sigma1": SelectField}

    def __init__(self, session, **kwargs):
        # You can pass name and other parameters if you want to
        super(TomoConfigView, self).__init__(TomoConfig, session,
                                             endpoint="tomoconfig",
                                             name="Config",
                                             category="Tomo",
                                             **kwargs)
    
    @expose('/edit/', methods=['GET', 'POST'])
    def edit_view(self):
        id = request.args.get('id')
        helpstring = default[id][0]
        helpstring = Markup(markdown.markdown(helpstring))
        self._template_args['helpstring'] = helpstring
        self._template_args['helpstringdefault'] = default[id][1]
        return super(TomoConfigView, self).edit_view()


def getitem(obj, item, default):
    if item not in obj:
        return default
    else:
        return obj[item]


# Job definitions

def register_job_types():
    jobtypes = []
    jobtypes.append( {"name":"TOMO_SAC", "after":"refstack"} )
    jobtypes.append({"name": "TOMO_FTAN", "after": "prepare_tomo"})
    return jobtypes
