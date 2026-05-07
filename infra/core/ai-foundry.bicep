targetScope = 'resourceGroup'

param location string
param tags object = {}
param aiFoundryResourceName string
param aiFoundryProjectName string
param deployments array = []
param connections array = []
@secure()
param connectionCredentials object = {}
param dependentResources array = []
param enableHostedAgents bool = true
param enableCapabilityHost bool = true
param enableMonitoring bool = true
param useExistingAiProject bool = false
param principalId string
param principalType string
param containerRegistryResourceId string = ''
param containerRegistryEndpoint string = ''
param acrConnectionName string = ''
param applicationInsightsConnectionString string = ''
param applicationInsightsResourceId string = ''
param applicationInsightsConnectionName string = ''

var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)
var effectiveAiAccountName = !empty(aiFoundryResourceName) ? aiFoundryResourceName : 'ai-account-${resourceToken}'
var effectiveAcrConnectionName = !empty(acrConnectionName) ? acrConnectionName : 'acr-${resourceToken}'
var effectiveAppInsightsConnectionName = !empty(applicationInsightsConnectionName) ? applicationInsightsConnectionName : 'appi-${resourceToken}'

resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (!useExistingAiProject) {
  name: effectiveAiAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: effectiveAiAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }

  @batchSize(1)
  resource modelDeployments 'deployments' = [
    for deployment in deployments: {
      name: deployment.name
      sku: deployment.?sku ?? {
        name: deployment.?skuName ?? 'Standard'
        capacity: deployment.?capacity ?? 1
      }
      properties: {
        model: deployment.?model ?? {
          format: 'OpenAI'
          name: deployment.?modelName ?? deployment.name
          version: deployment.?version ?? ''
        }
      }
    }
  ]

  resource project 'projects' = {
    name: aiFoundryProjectName
    location: location
    identity: {
      type: 'SystemAssigned'
    }
    properties: {
      description: '${aiFoundryProjectName} Project'
      displayName: aiFoundryProjectName
    }
    dependsOn: [
      modelDeployments
    ]
  }

  resource capabilityHost 'capabilityHosts@2025-10-01-preview' = if (enableHostedAgents && enableCapabilityHost) {
    name: 'agents'
    properties: {
      capabilityHostKind: 'Agents'
      enablePublicHostingEnvironment: true
    }
  }
}

resource existingAiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (useExistingAiProject) {
  name: effectiveAiAccountName

  resource project 'projects' existing = {
    name: aiFoundryProjectName
  }
}

resource localUserAzureAiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAiProject) {
  name: guid(subscription().id, resourceGroup().id, principalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  scope: aiAccount::project
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (!useExistingAiProject && enableMonitoring && !empty(applicationInsightsConnectionString) && !empty(applicationInsightsResourceId) && empty(applicationInsightsConnectionName)) {
  parent: aiAccount::project
  name: effectiveAppInsightsConnectionName
  properties: {
    category: 'AppInsights'
    target: applicationInsightsResourceId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: applicationInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsResourceId
    }
  }
}

resource acrConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (!useExistingAiProject && enableHostedAgents && !empty(containerRegistryResourceId) && !empty(containerRegistryEndpoint) && empty(acrConnectionName)) {
  parent: aiAccount::project
  name: effectiveAcrConnectionName
  properties: {
    category: 'ContainerRegistry'
    target: containerRegistryEndpoint
    authType: 'ManagedIdentity'
      isSharedToAll: true
      credentials: {
        clientId: aiAccount::project!.identity.principalId
        resourceId: containerRegistryResourceId
      }
    metadata: {
      ResourceId: containerRegistryResourceId
    }
  }
}

@batchSize(1)
resource customConnections 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = [for connection in connections: if (!useExistingAiProject) {
  parent: aiAccount::project
  name: connection.name
  properties: union({
    category: connection.category
    target: connection.target
    authType: connection.authType
    isSharedToAll: connection.?isSharedToAll ?? true
  }, contains(connectionCredentials, connection.name) ? {
    credentials: connectionCredentials[connection.name]
  } : {}, connection.?metadata != null ? {
    metadata: connection.metadata
  } : {})
}]

output accountName string = useExistingAiProject ? existingAiAccount.name : aiAccount.name
output accountId string = useExistingAiProject ? existingAiAccount.id : aiAccount.id
output projectName string = aiFoundryProjectName
output projectId string = useExistingAiProject ? existingAiAccount::project!.id : aiAccount::project!.id
output projectEndpoint string = useExistingAiProject ? existingAiAccount::project!.properties.endpoints['AI Foundry API'] : aiAccount::project!.properties.endpoints['AI Foundry API']
output openAiEndpoint string = useExistingAiProject ? existingAiAccount!.properties.endpoints['OpenAI Language Model Instance API'] : aiAccount!.properties.endpoints['OpenAI Language Model Instance API']
output projectPrincipalId string = useExistingAiProject ? '' : aiAccount::project!.identity.principalId
output acrConnectionName string = !empty(acrConnectionName) ? acrConnectionName : (!useExistingAiProject && enableHostedAgents && !empty(containerRegistryResourceId) && !empty(containerRegistryEndpoint) ? effectiveAcrConnectionName : '')
output applicationInsightsConnectionName string = !empty(applicationInsightsConnectionName) ? applicationInsightsConnectionName : (!useExistingAiProject && enableMonitoring && !empty(applicationInsightsConnectionString) && !empty(applicationInsightsResourceId) ? effectiveAppInsightsConnectionName : '')
output applicationInsightsConnectionString string = applicationInsightsConnectionString
output applicationInsightsResourceId string = applicationInsightsResourceId
output dependentResources object = {
  registry: {
    resourceId: containerRegistryResourceId
    loginServer: containerRegistryEndpoint
    connectionName: !empty(acrConnectionName) ? acrConnectionName : (!useExistingAiProject && enableHostedAgents && !empty(containerRegistryResourceId) && !empty(containerRegistryEndpoint) ? effectiveAcrConnectionName : '')
  }
  monitoring: {
    resourceId: applicationInsightsResourceId
    connectionName: !empty(applicationInsightsConnectionName) ? applicationInsightsConnectionName : (!useExistingAiProject && enableMonitoring && !empty(applicationInsightsConnectionString) && !empty(applicationInsightsResourceId) ? effectiveAppInsightsConnectionName : '')
  }
  requested: dependentResources
}
