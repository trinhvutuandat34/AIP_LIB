#pragma once
#include "../../behaviortree_cpp_v3\action_node.h"
#include "../../behaviortree_cpp_v3/bt_factory.h"
#include "../../../Geometry/Vector3.h"
#include "../Functions.h"
#include "../BlackBoard/CPPBlackBoard.h"

using namespace BT;

namespace Action
{
	class Task_LagDisplacementRoll : public SyncActionNode
	{
	private:


	public:


		Task_LagDisplacementRoll(const std::string& name, const NodeConfiguration& config) : SyncActionNode(name, config)
		{
		}

		~Task_LagDisplacementRoll()
		{

		}

		static PortsList providedPorts();

		NodeStatus tick() override;
	};
}
