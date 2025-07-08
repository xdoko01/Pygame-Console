''' Change Resolution Console Command 

    Examples of usage:
        "change_res"           ... get usage instructions
        "change_res -h"        ... get usage instructions
        "change_res --help"    ... get usage instructions
        "change_res 640 480"   ... change the resolution to 640x480
        "change_res 640 480 1" ... change the resolution to 640x480 + fullscreen
        "change_res 800 600 0" ... change the resolution to 800x600 + windowed
'''

instructions = """
Examples of usage:
    "change_res"           ... get usage instructions
    "change_res -h"        ... get usage instructions
    "change_res --help"    ... get usage instructions
    "change_res 640 480"   ... change the resolution to 640x480
    "change_res 640 480 1" ... change the resolution to 640x480 + fullscreen
    "change_res 800 600 0" ... change the resolution to 800x600 + windowed
"""

def initialize(register, module_name):
    '''Console Command registers itself at Console'''
    # Mandatory line
    register(fnc=cons_cmd_change_res, alias=module_name)

def cons_cmd_change_res(game_ctx, params):
    ''' Script that changes game resolution
    '''

    # Save all parameters passed from the Console in the list
    all_params = params.split()
    no_of_params = len(all_params) - 1 # exclude the script name

    # Show instructions if the last parametr indicates so
    if all_params[-1] in ('-h','--help', '?', 'help') or no_of_params < 2:
        print(instructions)

    # Try to set new resolution
    else:

        # Reinit the pygame screen
        fullscreen = bool(int(all_params[3])) if no_of_params > 2 else False
        game_ctx.init_display(res_x=int(all_params[1]), res_y=int(all_params[2]), fullscreen=fullscreen)

        # Tell console to change its resolution also
        game_ctx.console.init(app=game_ctx, width=int(all_params[1]), config=game_ctx.console_config)

