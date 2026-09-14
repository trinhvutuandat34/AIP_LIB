// Link against the project's Debug objects (excluding LibMain, dllmain and pch).
// Run with no argument to check disabled tracing; pass a CSV path to check enabled tracing.
#include <cassert>
#include <iostream>
#include "../GateTrace.h"
#include "behaviortree_cpp_v3/actions/always_success_node.h"

int main(int argc, char** argv)
{
    const bool enabled = argc > 1;
    _putenv_s("AIP_BT_GATE_TRACE", enabled ? argv[1] : "");
    BT::Tree tree;
    tree.nodes.push_back(std::make_shared<BT::AlwaysSuccessNode>("probe"));
    GateTrace::State state;
    GateTrace::Attach(state, tree);
    GateTrace::Attach(state, tree);
    assert(state.subs.size() == (enabled ? 1 : 0));
    CPPBlackBoard blackboard;
    for (int i = 0; i < 12000; ++i)
    {
        assert(tree.tickRoot() == BT::NodeStatus::SUCCESS);
        if (enabled)
            assert(state.pending == "probe:S");
        GateTrace::Record(state, tree, &blackboard, 1, 1);
        assert(state.pending.empty());
    }
    assert(state.ticks == (enabled ? 12000 : 0));
    std::cout << "PASS: tracing " << (enabled ? "enabled" : "disabled")
              << ", 12000 ticks, subscriptions=" << state.subs.size()
              << ", pending bytes=" << state.pending.size() << '\n';
}
