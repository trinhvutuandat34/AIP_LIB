#pragma once
#include "../../behaviortree_cpp_v3\action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include "../Functions.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class Task_OneCircleFight : public SyncActionNode
	{
	private:


	public:


		Task_OneCircleFight(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config)
		{
		}

		~Task_OneCircleFight()
		{

		}

		static PortsList providedPorts();

		NodeStatus tick() override;
	};
}
