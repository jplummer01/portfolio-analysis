// Assigns Azure AI User role to a principal on an AI Foundry project
// This allows the principal to invoke hosted agents via the invocations protocol

param aiAccountName string
param aiProjectName string
param principalId string
param principalType string = 'ServicePrincipal'

// Azure AI User role: 53ca6127-db72-4b80-b1b0-d745d6d5456d
var azureAiUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiAccountName

  resource project 'projects' existing = {
    name: aiProjectName
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, resourceGroup().id, principalId, azureAiUserRoleId, aiProjectName)
  scope: aiAccount::project
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', azureAiUserRoleId)
  }
}
