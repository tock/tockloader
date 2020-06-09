from .tbfh import TBFHeaderPadding

class PaddingApp:
	'''
	Representation of a placeholder app that is only padding between other apps.
	'''

	def __init__ (self, size):
		'''
		Create a `PaddingApp` based on the amount of size needing in the
		padding.
		'''
		self.tbf = TBFHeaderPadding(size)

	def get_header (self):
		'''
		Return the header for this padding.
		'''
		return self.tbf

	def get_size (self):
		'''
		Return the total size of the padding in bytes.
		'''
		return self.tbf.get_app_size()

	def get_binary (self, address):
		'''
		Return the binary array comprising the header and the padding between
		apps.
		'''
		tbfh_binary = self.tbf.get_binary()
		# Calculate the padding length.
		padding_binary_size = self.get_size() - len(tbfh_binary)
		return tbfh_binary + b'\0'*padding_binary_size

	def __str__ (self):
		return 'PaddingApp({})'.format(self.get_size())
