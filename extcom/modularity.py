#!/usr/bin/env python
# encoding: utf-8

#--------------------------------------------------
# modules
#--------------------------------------------------

from __future__ import division

from itertools import izip
from itertools import combinations
import copy

#--------------------------------------------------
# static variables
#--------------------------------------------------


#--------------------------------------------------
# private classes
#--------------------------------------------------
class _AbstractModularity(object):
	
	def __init__(self):
		self._modval = None

	def name(self):
		return self.__class__.__name__

	def value(self):
		return self._modval
	
	def calculate(self, status):
		""" Calculate the value of modularity.
		"""
		self._modval = self._calculate(status)
		return self._modval

	def _calculate(self, status):
		msg = 'modularity class should have _calculate function.'
		raise NotImplementedError(msg)

#--------------------------------------------------
# public classes
#--------------------------------------------------
class MurataModularity(_AbstractModularity):

	def _calculate(self, status):
		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()

		modval_from_com = [{} for _ in partlist]
		max_e_from_com = [{} for _ in partlist]
		modval = 0
		for corres, egnum_in_corres in status.com.iter_corres_egnum():
			e = egnum_in_corres / all_egnum

			a_multiplied = 1
			for part, com in izip(partlist, corres):
				egnum_from_com = status.com.egnum_from_com(part, com)
				a = egnum_from_com / all_egnum
				a_multiplied *= a

			partial_mod = e  - a_multiplied
			
			# whether max elmn or not for each community
			for part, com in izip(partlist, corres):
				max_e = max_e_from_com[part].get(com, 0)
				if e > max_e:
					max_e_from_com[part][com] = e
					modval -= modval_from_com[part].get(com, 0)
					modval_from_com[part][com] = partial_mod
					modval += partial_mod
		
		return modval / partnum

class NeubauerModularity(_AbstractModularity):

	def __init__(self, resolution = 1):
		_AbstractModularity.__init__(self)
		self._modval_from_corres = None
		self.resolution = resolution

	def _calculate(self, status):
		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()
		resolution = self.resolution

		modval_from_corres = {}
		mod = 0
		for corres, egnum_in_corres in status.com.iter_corres_egnum():
			e = egnum_in_corres / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = status.com.egnum_from_com(part, com)
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e - a_multiplied*resolution
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			mod += partial_mod
			modval_from_corres[corres] = partial_mod
			
		self._modval_from_corres = modval_from_corres
		return mod

	def calculate_diff(self, status, moving_diff_info):
		new_egnum_from_com = moving_diff_info['new_egnum_from_com']
		new_egnum_from_corres = moving_diff_info['new_egnum_from_corres']

		resolution = self.resolution

		modval_from_corres = self._modval_from_corres
		new_modval_from_corres = {}

		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()

		# revise modularity
		delta = 0
		for corres, egnum in new_egnum_from_corres.iteritems():
			#print "corres:"+str(corres)
			if egnum == 0:
				delta -= modval_from_corres.get(corres, 0)
				new_modval_from_corres[corres] = None
				continue

			e = egnum / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = new_egnum_from_com[part].get(
									com, 
									status.com.egnum_from_com(part, com) )
				#print str(part)+":"+str(com)+":"+str(egnum_from_com)
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e - a_multiplied*resolution
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			delta += partial_mod
			delta -= modval_from_corres.get(corres, 0)
			new_modval_from_corres[corres] = partial_mod

		# to prevent precision loss (桁落ち回避)
		if -0.00000009 < delta < 0.00000009:
			delta = 0

		# may be used later to reflect the moves
		modval_diff_info = {'delta_mod' : delta, 
							'new_modval_from_corres' : new_modval_from_corres}
		
		return delta, modval_diff_info
		
	def update_modval_with_diff_info(self, modval_diff_info):
		delta_modval = modval_diff_info['delta_mod']
		new_modval_from_corres = modval_diff_info['new_modval_from_corres']

		# update modval for each correspondence
		modval_from_corres = self._modval_from_corres
		for corres, modval in new_modval_from_corres.iteritems():
			if modval is None:
				del modval_from_corres[corres]
			else:
				modval_from_corres[corres] = modval

		# reflect modularity value
		self._modval += delta_modval

	def get_modval_from_corres(self):
		return self._modval_from_corres



class ThresholdModularity(_AbstractModularity):

	def __init__(self, threshold = 0, resolution = 1):
		_AbstractModularity.__init__(self)
		self.threshold = threshold
		self._modval_from_corres = None
		self.resolution = resolution

	def _calculate(self, status):
		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()
		modval_from_corres = {}
		rsol = self.resolution

		mod = 0
		for corres, egnum_in_corres in status.com.iter_corres_egnum():
			e = egnum_in_corres / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = status.com.egnum_from_com(part, com)
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e  - a_multiplied * rsol
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			if _mod > self.threshold:
				mod += partial_mod

			modval_from_corres[corres] = partial_mod

		self._modval_from_corres = modval_from_corres

		return mod
		
	def calculate_diff(self, status, moving_diff_info):
		new_egnum_from_com = moving_diff_info['new_egnum_from_com']
		new_egnum_from_corres = moving_diff_info['new_egnum_from_corres']

		threshold = self.threshold

		modval_from_corres = self._modval_from_corres
		new_modval_from_corres = {}

		rsol = self.resolution
		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()

		# revise modularity
		delta = 0
		for corres, egnum in new_egnum_from_corres.iteritems():
			if egnum == 0:
				tmp = modval_from_corres.get(corres, 0)
				if tmp > threshold :
					delta -= tmp
				new_modval_from_corres[corres] = None
				continue

			e = egnum / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = new_egnum_from_com[part].get(
									com, 
									status.com.egnum_from_com(part, com) )
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e - a_multiplied * rsol
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			if partial_mod > threshold:
				delta += partial_mod

			tmp = modval_from_corres.get(corres, 0)
			if tmp > threshold :
				delta -= tmp
			new_modval_from_corres[corres] = partial_mod

		# to prevent precision loss (桁落ち回避)
		if -0.00000009 < delta < 0.00000009:
			delta = 0

		# may be used later to reflect the moves
		modval_diff_info = {'delta_mod' : delta, 
							'new_modval_from_corres' : new_modval_from_corres}

		return delta, modval_diff_info
		
	def update_modval_with_diff_info(self, modval_diff_info):
		delta_modval = modval_diff_info['delta_mod']
		new_modval_from_corres = modval_diff_info['new_modval_from_corres']

		# update modval for each correspondence
		modval_from_corres = self._modval_from_corres
		for corres, modval in new_modval_from_corres.iteritems():
			if modval is None:
				del modval_from_corres[corres]
			else:
				modval_from_corres[corres] = modval

		# reflect modularity value
		self._modval += delta_modval

class PowerModularity(_AbstractModularity):

	def __init__(self, threshold = 0, power = 2, resolution = 1):
		_AbstractModularity.__init__(self)
		self.threshold = threshold
		self._modval_from_corres = None
		self.power = power
		self.resolution = resolution

	def _calculate(self, status):
		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()
		modval_from_corres = {}
		threshold = self.threshold
		power = self.power
		rsol =  self.resolution

		mod = 0
		for corres, egnum_in_corres in status.com.iter_corres_egnum():
			e = egnum_in_corres / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = status.com.egnum_from_com(part, com)
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e  - a_multiplied * rsol
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			if _mod > threshold:
				mod += pow(partial_mod, power)

			modval_from_corres[corres] = partial_mod

		self._modval_from_corres = modval_from_corres

		return mod
		
	def calculate_diff(self, status, moving_diff_info):
		new_egnum_from_com = moving_diff_info['new_egnum_from_com']
		new_egnum_from_corres = moving_diff_info['new_egnum_from_corres']

		modval_from_corres = self._modval_from_corres
		new_modval_from_corres = {}

		threshold = self.threshold
		power = self.power
		rsol = self.resolution

		partnum = status.basic.partnum()
		partlist = status.basic.partlist()
		all_egnum = status.basic.edgenum()

		# revise modularity
		delta = 0
		for corres, egnum in new_egnum_from_corres.iteritems():
			if egnum == 0:
				tmp = modval_from_corres.get(corres, 0)
				if tmp > threshold :
					delta -= pow(tmp,power)
				new_modval_from_corres[corres] = None
				continue

			e = egnum / all_egnum
			a_multiplied = 1
			a_inv_sum = 0
			for part, com in izip(partlist, corres):
				egnum_from_com = new_egnum_from_com[part].get(
									com, 
									status.com.egnum_from_com(part, com) )
				a = egnum_from_com / all_egnum
				a_multiplied *= a
				a_inv_sum += 1 / a

			_mod = e - a_multiplied * rsol
			alpha = e * a_inv_sum * (1 / partnum)
			partial_mod = _mod * alpha

			if partial_mod > threshold:
				delta += pow(partial_mod,power)
			#else:
				#print "PM under the threshold:%f"%(partial_mod)
			tmp = modval_from_corres.get(corres, 0)
			if tmp > threshold :
				delta -= pow(tmp,power)
			new_modval_from_corres[corres] = partial_mod

		# to prevent precision loss (桁落ち回避)
		if -0.00000009 < delta < 0.00000009:
			delta = 0

		# may be used later to reflect the moves
		modval_diff_info = {'delta_mod' : delta, 
							'new_modval_from_corres' : new_modval_from_corres}

		return delta, modval_diff_info
		
	def update_modval_with_diff_info(self, modval_diff_info):
		delta_modval = modval_diff_info['delta_mod']
		new_modval_from_corres = modval_diff_info['new_modval_from_corres']

		# update modval for each correspondence
		modval_from_corres = self._modval_from_corres
		for corres, modval in new_modval_from_corres.iteritems():
			if modval is None:
				del modval_from_corres[corres]
			else:
				modval_from_corres[corres] = modval

		# reflect modularity value
		self._modval += delta_modval

#Newman modularity for adjacent edge network
class NewmanModularity(_AbstractModularity):

	def __init__(self, resolution = 0):
		self._resolution = resolution
		self._modval = 0
		self._modval_from_egcls = None
		self._sum_degree = None
		self._egset_of_edges = None
		edge_degree = None

	#require egcls have unique label
	def _calculate(self, status):
		modval_from_egcls = {}
		modval = 0
		resolution = self._resolution
		edgenum = status.basic.edgenum()
		edge_degree = {}
		egset_of_edges = {}

		#initilize edgelist_of_edges, edge_degree
		for edge in range(edgenum):
			egset_of_edges[edge] = status.hiegcl.adj_egset_for_part(edge)
			edge_degree[edge] = len(egset_of_edges[edge])

		#sum up partial modularity
		sum_degree = sum(edge_degree.values())
		for egcl in status.hiegcl.egcls_orderly():
			egcl_label = status.hiegcl.label_of_egcl(egcl)
			modval_from_egcls[egcl_label] = 0
			for edge1, edge2 in combinations(status.hiegcl.egset_of_egcl(egcl),2):
				partial_mod = 0
				if edge1 in egset_of_edges[edge2]:
					partial_mod += 1
				partial_mod -= resolution * edge_degree[edge1] * edge_degree[edge2] / sum_degree
				partial_mod /= sum_degree
				modval_from_egcls[egcl_label] += partial_mod

		self._edge_degree = edge_degree
		self._egset_of_edges = egset_of_edges
		self._modval_from_egcls = modval_from_egcls
		self._sum_degree = sum_degree
		modval = sum(modval_from_egcls.values())
		return modval

	def calculate_diff(self, status, egcl_label, next_egcl_label):
		sum_degree = self._sum_degree
		modval_from_egcls = self._modval_from_egcls
		egset_of_edges = self._egset_of_edges
		edge_degree = self._edge_degree
		resolution = self._resolution
		resolution = 1

		delta = 0
		#collect up edges for each egcl label
		egset1 = set()
		egset2 = set()
		for egcl in status.hiegcl.egclset_of_label(egcl_label):
			egset1 |= status.hiegcl.egset_of_egcl(egcl)
		for next_egcl in status.hiegcl.egclset_of_label(next_egcl_label):
			egset2 |= status.hiegcl.egset_of_egcl(next_egcl)

		#add delta modularity when the edges of egcl move to next egcl label
		for edge1 in egset1:
			for edge2 in egset2:
				partial_mod = 0
				if edge1 in egset_of_edges[edge2]:
					partial_mod += 1
				partial_mod -= resolution * edge_degree[edge1] * edge_degree[edge2] / sum_degree
				partial_mod /= sum_degree
				delta += partial_mod
		delta -= modval_from_egcls[egcl_label]
		delta -= modval_from_egcls[next_egcl_label]

		# to prevent precision loss
		if -0.00000009 < delta < 0.00000009:
			delta = 0

		modval_diff_info = {'delta':delta,
							'prev_egcl_label':egcl_label,
							'next_egcl_label':next_egcl_label}

		return delta, modval_diff_info


	def update_modval_with_diff_info(self, modval_diff_info):
		prev_egcl_label = modval_diff_info['prev_egcl_label']
		next_egcl_label = modval_diff_info['next_egcl_label']
		delta = modval_diff_info['delta']
		#update modval information
		self._modval_from_egcls[next_egcl_label] += self._modval_from_egcls[prev_egcl_label] + delta
		self._modval_from_egcls[prev_egcl_label] = 0
		self._modval += delta



#--------------------------------------------------
# test
#--------------------------------------------------
def _test_modularity(status, mod_list, answer_list):
	for ind, mod in enumerate(mod_list):
		modname = mod.name()
		modval = mod.calculate(status)
		ans = answer_list[ind]
		tn = modval == ans
		print "    %-40s : %.5f (ans: %.5f), %s" % (modname, modval, ans, tn)
	print ''

def _test_delta_calculation(modularity, moved_vrts_info, answer):
	moving_diff = status.com.diff_of_moving_vrts(moved_vrts_info)
	delta, modval_diff = modularity.calculate_diff(status, moving_diff)
	modval = modularity.value() + delta
	ans = answer
	tn = modval == answer
	print "    mod: %.5f (del: %.5f), ans: %.5f, %s" % (modval, delta, ans, tn)
	status.com.update_com_with_diff_info(moving_diff)
	modularity.update_modval_with_diff_info(modval_diff)

if __name__ == "__main__":
	from _status import NetworkStatus
	edge_list = [[0, 0, 0], [0, 0, 1], [1, 1, 0], [1, 1, 1],
				 [2, 2, 2], [2, 2, 3], [3, 3, 2], [3, 3, 3]]
	status = NetworkStatus(edge_list)
	status.add_com()

	##############################################
	# TEST: modularity calculation
	##############################################
	print 'Modularity calcuation test'
	mod_list = [NeubauerModularity(),
				MurataModularity(),
				ThresholdModularity(),
				PowerModularity(power=2)]

	# modularity calculation, test 1
	print '  All vertices are same community'
	com_labels = [[0, 0, 0, 0],
				  [0, 0, 0, 0],
				  [0, 0, 0, 0]]
	answer_list = [0.0, 0.0, 0.0, 0.0]
	status.com.set_com_labels(com_labels)
	_test_modularity(status, mod_list, answer_list)

	# modularity calculation, test 2
	print '  Idealistic community structure for this network (probably)'
	com_labels = [[0, 0, 1, 1],
				  [0, 0, 1, 1],
				  [0, 0, 1, 1]]
	answer_list = [0.75, 0.75, 0.75, 0.28125]
	status.com.set_com_labels(com_labels)
	_test_modularity(status, mod_list, answer_list)

	# modularity calculation, test 3
	print '  Asymetric community structure'
	com_labels = [[0, 1, 1, 1],
				  [0, 1, 1, 1],
				  [0, 0, 0, 0]]
	answer_list = [0.3125, 0.3125, 0.3125, 0.04931640625]
	status.com.set_com_labels(com_labels)
	_test_modularity(status, mod_list, answer_list)

	#exit()

	##############################################
	# TEST: delta calculation
	##############################################
	print 'Delta calcuation test'
	com_labels = [[0, 0, 0, 0],
				  [0, 0, 0, 0],
				  [0, 0, 0, 0]]
	modularity = NeubauerModularity()
	status.com.set_com_labels(com_labels)
	modval = modularity.calculate(status)
	print "    %.5f (first modularity value)" % modval

	# delta calculation, test 1
	moved_vrts_info = ({2 : [0, 1],
						3 : [0, 1]},
					   {2 : [0, 1],
						3 : [0, 1]},
					   {2 : [0, 1],
						3 : [0, 1]})
	answer = 0.75
	_test_delta_calculation(modularity, moved_vrts_info, answer)

	# delta calculation, test 2
	moved_vrts_info = ({1 : [0, 1]},
					   {1 : [0, 1]},
					   {2 : [1, 0],
						3 : [1, 0]})
	answer = 0.3125
	_test_delta_calculation(modularity, moved_vrts_info, answer)

	# delta calculation, test 3
	moved_vrts_info = ({0 : [0, 1]},
					   {0 : [0, 1]},
					   {})
	answer = 0.0
	_test_delta_calculation(modularity, moved_vrts_info, answer)
  
