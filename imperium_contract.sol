// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Imperium {
    struct Project {
        string name;
        string description;
        uint256 fundingGoal;
        uint256 currentFunding;
        uint256 voteCount;
        address payable creator;
        bool funded;
    }

    mapping(uint256 => Project) public projects;
    mapping(address => uint256) public memberVotes;
    mapping(address => uint256) public memberContributions;

    uint256 public projectCount;
    uint256 public totalVotes;
    uint256 public totalContributions;

    address public owner;

    event ProjectCreated(uint256 projectId, string name, address creator);
    event ProjectFunded(uint256 projectId, string name, uint256 fundingAmount);
    event VoteCasted(uint256 projectId, string name, address voter);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only the contract owner can call this function.");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function createProject(string memory _name, string memory _description, uint256 _fundingGoal) external {
        require(_fundingGoal > 0, "Funding goal must be greater than zero.");

        projectCount++;
        projects[projectCount] = Project(
            _name,
            _description,
            _fundingGoal,
            0,
            0,
            payable(msg.sender),
            false
        );

        emit ProjectCreated(projectCount, _name, msg.sender);
    }

    function fundProject(uint256 _projectId) external payable {
        require(_projectId > 0 && _projectId <= projectCount, "Invalid project ID.");
        require(!projects[_projectId].funded, "Project has already been funded.");
        require(msg.value > 0, "Funding amount must be greater than zero.");

        Project storage project = projects[_projectId];
        project.currentFunding += msg.value;
        totalContributions += msg.value;

        if (project.currentFunding >= project.fundingGoal) {
            project.funded = true;
            emit ProjectFunded(_projectId, project.name, project.currentFunding);
        }
    }

    function castVote(uint256 _projectId) external {
        require(_projectId > 0 && _projectId <= projectCount, "Invalid project ID.");
        require(projects[_projectId].funded, "Project has not been funded yet.");

        Project storage project = projects[_projectId];
        require(memberVotes[msg.sender] == 0, "You have already casted your vote for this round.");

        project.voteCount++;
        memberVotes[msg.sender] = _projectId;
        totalVotes++;

        emit VoteCasted(_projectId, project.name, msg.sender);
    }

    function getProjectDetails(uint256 _projectId) external view returns (
        string memory name,
        string memory description,
        uint256 fundingGoal,
        uint256 currentFunding,
        uint256 voteCount,
        address creator,
        bool funded
    ) {
        require(_projectId > 0 && _projectId <= projectCount, "Invalid project ID.");

        Project storage project = projects[_projectId];
        return (
            project.name,
            project.description,
            project.fundingGoal,
            project.currentFunding,
            project.voteCount,
            project.creator,
            project.funded
        );
    }

    function getMemberVotes(address _member) external view returns (uint256) {
        return memberVotes[_member];
    }

    function getMemberContributions(address _member) external view returns (uint256) {
        return memberContributions[_member];
    }

    function withdrawFunds() external onlyOwner {
        require(address(this).balance > 0, "No funds available for withdrawal.");

        payable(owner).transfer(address(this).balance);
    }
}
