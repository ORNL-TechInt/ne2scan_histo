#!/usr/bin/python
'''
Created on Sep 20, 2013

@author: xmr

@summary: Reads an ne2scan output file from stdin and writes a csv file
containing file age data in a format suitable for generating histograms
easily in a spreadsheet program.
'''

import collections
import sys
import os
import argparse

# ----------------------------------------------------------------------------
# Some constants we're going to want later

# Labels for the histogram bins
BIN_LABELS = ["<1", "<5", "<7", "<14", "<30", "<60", "<90", "90+"] # these are in days

# Number of days each bin represents (corresponding to the labels above)
BIN_DAYS = [1.0, 5.0, 7.0, 14.0, 30.0, 60.0, 90.0]
# Note that there's no value equivalent to the "90+" label.  If a file age fails
# all the other tests, it will go in the 90+ column

# This exists to make it easy to initialize new nodes in the B-Tree we're going
# to build up.
# If I ever change BIN_LABLES, I just change this constant, too, instead of
# mucking about in various places in the code.
EMPTY_HISTO_DATA = [0, 0, 0, 0, 0, 0, 0, 0]
# ----------------------------------------------------------------------------

def memoize(fn):
    cached_results = {}
    
    def memoized( *args):
        try:
            return cached_results[args]
        except KeyError:
            # no cached result - calculate it for real
            result = fn(*args)
            
            if result != None:
                # don't store a None in the cache
                cached_results[args] = result
            return result
    return memoized
            


class HistoTree(object):
    '''
    This is a BTree implementation for storing our histogram data.  Each node
    stores a directory name, a list of bin values (initialized from 
    EMPTY_HISTO_DATA above), a parent pointer and multiple child pointers.
    '''

    def __init__(self):
        
        # These should all be references to HistoNode objects
        self._traverse_nodes = collections.deque() #[]   # Used to keep track of where we are in 
                                    # the traverse operation
        # Initialize the top node of the tree
        self._root = self.HistoNode('ROOT', None)
        
        
    def insert(self, full_path_name):
        '''
        Inserts a new node into the tree
        
        full_path_name should just be the directories; it should not include
        a file name at the end.
        '''
       
        # split full path into its elements (each element is one level
        # in the tree)
        dirs = full_path_name.strip().split( os.sep)
        # the first element in dirs should be '.' and the second should be
        # 'ROOT'.  Skip them.
        if dirs[0] != '.' or \
           dirs[1] != 'ROOT':
            raise self.InvalidPathError( full_path_name)
        
        dirs = dirs[2:]
        
        node = self._root
        for one_dir in dirs:
            new_node = node.get_child( one_dir)
            if new_node == None:
                # Well, the node wasn't found - let's create it.
                new_node = self.HistoNode( one_dir, node)
                node.add_child( new_node)
            node = new_node
    
#    @memoize
#    def find(self, full_path_name):
#        '''
#        Returns a reference to the HistoNode for the specified path (or
#        None if the path doesn't exist)
#        '''
#        
#        # split full path into its elements (each element is one level
#        # in the tree)
#        dirs = full_path_name.split( os.sep)
#        # the first element in dirs should be '.' and the second should be
#        # 'ROOT'.  Skip them.
#        if dirs[0] != '.' or \
#           dirs[1] != 'ROOT':
#            raise self.InvalidPathError( full_path_name)
#        
#        dirs = dirs[2:]
#        
#        node = self._root
#        for one_dir in dirs:
#            new_node = node.get_child( one_dir)
#            if new_node == None:
#                return None
#            else:
#                node = new_node
#        return node

    @memoize
    def find(self, full_path_name):
        '''
        Returns a reference to the HistoNode for the specified path (or
        None if the path doesn't exist)
        
        This is a recursive implementation (which makes better use of
        the memoized results than the non-recursive implementation)
        '''       
        (dir_path, last_part) = os.path.split( full_path_name)
        
        if dir_path == "./ROOT":
            return self._root.get_child(last_part)
        elif dir_path == "":
            raise self.InvalidPathError( full_path_name)
        else:
            parent_node = self.find(dir_path)
            if parent_node == None:
                return None
            else:
                return parent_node.get_child( last_part)
        
        
        
    def increment(self, full_path_name, age):
        '''
        Increments the appropriate bin for the specified node
        
        Age is specified in days
        '''        
            
        node = self.find(full_path_name)
        if (node == None):
            raise self.InvalidPathError( full_path_name)
        
        bin_num = 0;
        for days in BIN_DAYS:
            if age >= days:
                bin_num += 1
            else:
                break
 
        node.data[bin_num] += 1
        
    def full_path_name(self, node):
        '''
        Returns the full path name (as a string) for the specified node
        '''
        
        pathname = node.name
        while node.parent != None:
            node = node.parent
            pathname = node.name + os.sep + pathname
        
        return pathname
        
    def traverse_start(self):
        '''
        Initializes a breadth-first traverse of the tree
        '''
        self._traverse_nodes.append( self._root)
        
    def traverse_next(self):
        '''
        One iteration of the traverse.
        Returns a tuple of the full path for the particular node and its
        histogram data. 
        '''
        
        # Sanity check 
        if len( self._traverse_nodes) == 0:
            # Empty node list means the traverse is done (or was never started)
            return (None, None)
        
        node = self._traverse_nodes.popleft()
        child_keys = node.children.keys()
        child_keys.sort()
        for key in child_keys:
            self._traverse_nodes.append(node.children[key])
           
        return (self.full_path_name( node), node.data)
    
    def summarize_histo_data(self):
        '''
        Walk the tree (depth-first), adding each child's histogram values to its parent's values
        '''
        self._root.summarize_histo_data()

    
    # exception raised when a bad path is passed to insert()   
    class InvalidPathError( Exception):
        pass
    
    class HistoNode(object):
        __slots__ = "parent", "children", "name", "data"
        # parent should be a reference to another HistoNode (or None in the
        # special case of the root node)
        # children should be a list of (possibly empty) HistoNode references
        # name
        # data is a list initialized from EMPTY_HISTO_DATA above..
        
        def __init__(self, name, parent):
            self.children = {}  # The keys will be the children's names,
                                # values are referenecs to HistoNodes
            
            # Can't just assign to data to EMPTY_HISTO_DATA or else
            # every HistNode will have a reference to the same object!
            self.data = []
            self.data.extend(EMPTY_HISTO_DATA)
            
            self.parent = parent
            self.name = name
        
        def get_child(self, name):
            '''
            Returns a reference to a HistoNode object with the specified name,
            or None if the name wasn't found.
            '''
            return self.children.get(name) # returns None if name doesn't exist
            
                
        def add_child(self, child):
            self.children[child.name] = child
            # TODO: should we check to ensure we aren't overwriting an
            # existing child?
            
        def summarize_histo_data(self):
            '''
            Adds the histogram data from all child nodes to the current node
            '''
            for child in self.children.values():
                child.summarize_histo_data()
                
                for i in range( len( self.data)):
                    self.data[i] += child.data[i]
            
            
             

def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile",
                        help="Specify the name of the input file.  (Default is to read from stdin.)")
                        
    parser.add_argument("-o", "--outfile",
                        help="Specify the name of the output file.  (Default is to write to stdout.)")
    main_args = parser.parse_args()
    
    
    if main_args.infile > 0:
        infile = open( main_args.infile, 'r')
    else:
        infile = sys.stdin    

    if main_args.outfile > 0:
        outfile = open( main_args.outfile, 'w')
    else:
        outfile = sys.stdout
    
    tree = HistoTree()
    
    first_line = infile.readline()
    scan_time = int(first_line.split('|')[3]) # the time the scan was run
        
    # Read lines from stdin, parse them & add them to the tree
    infile.readline()  # we don't care bout the 2nd line in the file 
    line = infile.readline()
    line_no = 3;  # line counter.  Useful for debugging corrupt input files
    while line[0:10] != "#complete#":
        parts = line.split('|')
        
        # We only care about files (not directories) and the name must start
        # with "./ROOT" (field 8 contains OST ID's if it's a file, and is 
        # empty for directories)
        try:
            if len(parts[8]) > 0 and parts[9][0:6] == './ROOT':
      
                # Get the most recent of atime, ctime & mtime
                file_time = max( int(parts[0]), int(parts[1]), int(parts[2]))
                # Because ne2scan takes so long, it's possible that files might
                # be updated after the scan has started but before the scan
                # reaches them.  That would result in a negative age. This
                # isn't really a problem since all we do is a 'less than'
                # but it's worth pointing out.
                age = (scan_time - file_time) / 86400.0  # age is in days
                
                (dir_path, filename) = os.path.split( parts[9])
                try:
                    tree.increment(dir_path, age)
                except HistoTree.InvalidPathError:
                    # if we get one of these, it's because we haven't inserted
                    # a node for this directory yet
                    tree.insert( dir_path)
                    tree.increment(dir_path, age)  
        except IndexError, ex:
            sys.stderr.write( "Error parsing line %d: %s\n"%(line_no, ex.message))
        line = infile.readline()
        line_no += 1
    
    # Done reading in our data.  At this point, the histogram values for each
    # directory only count files in that directory.  What we want is for them
    # to include files in the directory and all the child directories
    tree.summarize_histo_data()
     
    # Now write the output in CSV format
    out = "Directory"
    for item in BIN_LABELS:
        out += ", %s"% item
    out += "\n"
    
    outfile.write( out)
    
    tree.traverse_start()    
    (the_dir, data) = tree.traverse_next()
    while the_dir != None:
        out = the_dir
        for item in data:
            out += ", %d"%item
        out += "\n"
        outfile.write( out)
        (the_dir, data) = tree.traverse_next()
    
    

if __name__ == '__main__':
    # Verify that we've at least got version 2.6
    # (Older versions didn't have the message field in their exception
    # classes.)
    if sys.hexversion >= 0x02060000:
        main()
    else:
        sys.stderr.write( 'Python interpreter is too old.  This script requires at least v2.6\n')
        sys.stderr.write( 'Python version string:\n')
        sys.stderr.write( sys.version)
        sys.stderr.write( '\n')
        
