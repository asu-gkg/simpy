CXX = g++
CXXFLAGS = -I. -Icsg-htsim/sim -Icsg-htsim/sim/datacenter -std=c++11 -g -O2
LDFLAGS = 

# Source files
SRCS = test_cpp_comparison.cpp \
       csg-htsim/sim/eventlist.cpp \
       csg-htsim/sim/network.cpp \
       csg-htsim/sim/queue.cpp \
       csg-htsim/sim/compositeprioqueue.cpp \
       csg-htsim/sim/loggers.cpp \
       csg-htsim/sim/config.cpp \
       csg-htsim/sim/logfile.cpp

# Object files
OBJS = $(SRCS:.cpp=.o)

# Target
TARGET = test_cpp_comparison

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all clean