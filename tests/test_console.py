''' Tests of the Console/Header/TextOutput behaviour. Runs headless (dummy SDL video driver),
so no window is opened and the tests can run on CI.
'''
import io
import os
import sys

import pytest

# Headless pygame - must be set before pygame.display is used
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import pygame

from pgconsole import Console, CommandLineProcessor, Header, StdIOOutput

FONT = os.path.join(ROOT, 'examples', 'fonts', 'truetype', 'IBMPlexMono-Regular.ttf')


class DummyApp:
	''' Stand-in for the game instance referenced by the console.
	'''
	def cons_get_pos(self):
		return '0,0'


@pytest.fixture(scope='module', autouse=True)
def display():
	pygame.init()
	surface = pygame.display.set_mode((800, 600))
	yield surface
	pygame.quit()


@pytest.fixture
def config():
	return {
		'global': {
			'padding': (5, 5, 5, 5),
			'welcome_msg': 'welcome',
		},
		'output': {
			'font_file': FONT,
			'font_size': 14,
			'display_lines': 5,
			'buffer_size': 10,
		},
		'input': {
			'font_file': FONT,
			'font_size': 14,
			'prompt': '>',
		},
	}


@pytest.fixture
def console(config, display):
	return Console(DummyApp(), 800, config)


#####
# Header layouts (#16, #17)
#####

@pytest.mark.parametrize('layout_name', Header.LAYOUTS)
def test_header_layouts_do_not_crash(layout_name, display):
	''' Every header layout must survive show(), also with a font background color set.
	'''
	header_config = {
		'font_file': FONT,
		'text': 'Scrolling header text',
		'layout': [layout_name, 0, 2],
		'font_bck_color': (10, 20, 30),
	}
	console = Console(DummyApp(), 800, {'header': header_config})

	# More frames, so that the scrolling offset is really recalculated and wraps around
	for _ in range(5):
		console.console_header.show(display, (0, 0))


def test_scroll_layouts_move_the_text(display):
	''' The non-continuous scroll layouts must change the offset over time.
	'''
	for layout_name, direction in (('SCROLL_LEFT', -1), ('SCROLL_RIGHT', 1)):
		header = Header(Console(DummyApp(), 800, {}), 800, {
			'font_file': FONT,
			'text': 'x' * 50,
			'layout': [layout_name, 0, 3],
		})
		offset_before = header.scroll_offset
		header.scroll_last_time = 0  # make sure the time gate opens
		header.show(display, (0, 0))
		assert (header.scroll_offset - offset_before) * direction > 0, layout_name


#####
# Output buffer trimming (#19, #26)
#####

def test_buffers_are_trimmed_to_buffer_size(console):
	output = console.console_output
	console.clear()

	for i in range(40):
		output.write(f'line {i}')

	assert len(output.buffer) == output.buffer_size
	assert len(output.unprocessed_buffer) == output.buffer_size

	# The oldest rows must be the ones that were dropped - order is kept
	assert output.unprocessed_buffer[-1][0] == 'line 39'
	assert output.unprocessed_buffer[0][0] == f'line {40 - output.buffer_size}'
	assert output.buffer[-1][0] == 'line 39'


def test_unprocessed_buffer_is_trimmed_independently(console):
	''' Texts consisting of newlines only add a row to the unprocessed buffer but no row to
	the wrapped one. The trimming must not index one buffer by the length of the other (#19).
	'''
	output = console.console_output
	console.clear()

	written = []
	for i in range(3):
		output.write(f'line {i}')
		written.append((f'line {i}', None))

	# The color makes the otherwise identical newline rows distinguishable
	for i in range(output.buffer_size + 2):
		output.write('\n', color=(i, 0, 0))
		written.append(('\n', (i, 0, 0)))

	# Exactly the last buffer_size written texts, in the order they were written
	assert output.unprocessed_buffer == written[-output.buffer_size:]


def test_trimming_keeps_the_buffer_identity(console):
	''' Trimming must happen in place - Console.init() hands the very same list around.
	'''
	output = console.console_output
	buffer_before = output.unprocessed_buffer

	for i in range(3 * output.buffer_size):
		output.write(f'line {i}')

	assert output.unprocessed_buffer is buffer_before


#####
# clear() and reset() (#14, #15)
#####

def test_clear_empties_the_buffers(console):
	console.write('some text')
	console.console_output.buffer_offset = 1

	console.clear()

	assert console.console_output.buffer == []
	assert console.console_output.unprocessed_buffer == []
	assert console.console_output.buffer_offset == 0
	assert not hasattr(console.console_output, 'log')  # the old, wrong attribute


def test_reset_reloads_and_clears_the_console(console):
	console.write('some text')
	console.console_input.text = 'half typed command'

	console.reset()

	assert console.console_output.buffer == []
	assert console.console_output.unprocessed_buffer == []
	assert console.console_input.get_text() == ''
	# The console is still usable after the reset
	console.write('after reset')
	assert console.console_output.unprocessed_buffer[-1][0] == 'after reset'


#####
# Deferred rendering (#13)
#####

def test_defer_render_renders_once_per_frame(console, monkeypatch):
	renders = []
	original = console.console_output.prepare_surface
	monkeypatch.setattr(console.console_output, 'prepare_surface',
						lambda *a, **kw: (renders.append(1), original(*a, **kw))[1])

	for i in range(10):
		console.write(f'line {i}', defer_render=True)
	assert renders == []
	assert console.output_render_pending

	console.update([])
	assert len(renders) == 1
	assert not console.output_render_pending

	console.update([])  # nothing pending anymore
	assert len(renders) == 1


#####
# Injectable dispatcher (#10)
#####

def test_cli_factory_is_used_and_remembered(config, display):
	class MyCLI(CommandLineProcessor):
		pass

	console = Console(DummyApp(), 800, config, cli_factory=MyCLI)
	assert isinstance(console.cli, MyCLI)

	# Must survive re-init, which is what change_res does
	console.init(width=640, config=config, app=console.app)
	assert isinstance(console.cli, MyCLI)


def test_cli_class_config_key(config, display, monkeypatch):
	module = type(sys)('fake_cli_module')
	module.MyCLI = type('MyCLI', (CommandLineProcessor,), {})
	monkeypatch.setitem(sys.modules, 'fake_cli_module', module)

	for spec in ('fake_cli_module.MyCLI', 'fake_cli_module:MyCLI'):
		config['global']['cli_class'] = spec
		console = Console(DummyApp(), 800, config)
		assert isinstance(console.cli, module.MyCLI), spec


@pytest.mark.parametrize('spec', ['no_such_module.MyCLI', 'pgconsole.NoSuchClass', 'NoDots'])
def test_invalid_cli_class_raises_value_error(spec, config, display):
	config['global']['cli_class'] = spec
	with pytest.raises(ValueError):
		Console(DummyApp(), 800, config)


def test_config_without_global_section(display):
	''' A configuration with no global section must be legal (#18).
	'''
	console = Console(DummyApp(), 800, {'header': {'font_file': FONT, 'text': 'header'}})
	assert isinstance(console.cli, CommandLineProcessor)


#####
# Standard IO output (#27)
#####

def test_cli_supports_color_on_standard_io():
	''' Without a graphical output the dispatcher writes to a plain stream, which must
	still accept the color parameter.
	'''
	stream = io.StringIO()
	cli = CommandLineProcessor(DummyApp(), output=stream, cmd_pckg_path='examples.commands')

	assert isinstance(cli.output, StdIOOutput)

	cli.do_list('')  # writes with color=font_color_info
	written = stream.getvalue()

	assert 'Registered commands' in written
	assert '\x1b[' not in written  # StringIO is not a terminal - no escape sequences


def test_stdio_output_colors_only_on_terminal():
	class FakeTTY(io.StringIO):
		def isatty(self):
			return True

	tty_out = StdIOOutput(FakeTTY())
	tty_out.write('colored', color=(1, 2, 3))
	assert tty_out.stream.getvalue() == '\x1b[38;2;1;2;3mcolored\x1b[0m\n'

	plain_out = StdIOOutput(io.StringIO())
	plain_out.write('plain', color=(1, 2, 3))
	assert plain_out.stream.getvalue() == 'plain\n'

	# A single newline only, no matter whether the text brings one
	plain_out = StdIOOutput(io.StringIO())
	plain_out.write('with newline\n')
	assert plain_out.stream.getvalue() == 'with newline\n'

	# Not a RGB tuple - written as it is instead of crashing
	tty_out = StdIOOutput(FakeTTY())
	tty_out.write('bad color', color='red')
	assert tty_out.stream.getvalue() == 'bad color\n'
