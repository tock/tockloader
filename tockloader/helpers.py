'''
Various helper functions that tockloader uses. Mostly for interacting with
users in a nice way.
'''

import colorama

def set_terminal_title (title):
	print(colorama.ansi.set_title(title))

def set_terminal_title_from_port_info (info):
	'''
	Set a terminal title from a `pyserial` object.
	'''
	extras = ['Tockloader']
	if info.manufacturer and info.manufacturer != 'n/a':
		extras.append(info.manufacturer)
	if info.name and info.name != 'n/a':
		extras.append(info.name)
	if info.description and info.description != 'n/a':
		extras.append(info.description)
	#if info.hwid and info.hwid != 'n/a':
	#	extras.append(info.hwid)
	if info.product and info.product != 'n/a':
		if info.product != info.description:
			extras.append(info.product)
	title = ' : '.join(extras)

	set_terminal_title(title)

def set_terminal_title_from_port (port):
	'''
	Set the title of the user's terminal for Tockloader.
	'''
	set_terminal_title('Tockloader : {}'.format(port))

def menu (options, *, return_type, default_index=0, prompt='Which option? ', title=''):
	'''
	Present a menu of choices to a user

	`options` should be a like-list object whose iterated objects can be coerced
	into strings.

	`return_type` must be set to one of
	  - "index" - for the index into the options array
	  - "value" - for the option value chosen

	`default_index` is the index to present as the default value (what happens
	if the user simply presses enter). Passing `None` disables default
	selection.
	'''
	prompt_to_show = prompt
	print(title)
	for i,opt in enumerate(options):
		print('[{}]\t{}'.format(i, opt))
	if default_index is not None:
		prompt_to_show += '[{}] '.format(default_index)
	print()

	resp = input(prompt_to_show)
	if resp == '':
		resp = default_index
	else:
		try:
			resp = int(resp)
			if resp < 0 or resp >= len(options):
				raise ValueError
		except:
			return menu(options,
				        return_type=return_type,
				        default_index=default_index,
				        prompt=prompt,
				        title=title)

	if return_type == 'index':
		return resp
	elif return_type == 'value':
		return options[resp]
	else:
		raise NotImplementedError('Menu caller asked for bad return_type')

def plural (value):
	'''
	Return '' or 's' based on whether the `value` means a string should have
	a plural word.

	`value` can be a list or a number. If the number or the length of the list
	is 1, then '' will be returned. Otherwise 's'.
	'''
	try:
		value = len(value)
	except:
		pass
	if value == 1:
		return ''
	else:
		return 's'
