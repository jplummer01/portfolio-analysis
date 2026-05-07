targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string

@minLength(1)
@maxLength(90)
param resourceGroupName string = 'rg-${environmentName}'

// AI Foundry parameters (populated by the azd ai agents extension)
param aiFoundryResourceName string = ''
param aiFoundryProjectName string = 'ai-project-${environmentName}'
param aiProjectDeploymentsJson string = '[]'
param aiProjectConnectionsJson string = '[]'
@secure()
param aiProjectConnectionCredentialsJson string = ''
param aiProjectDependentResourcesJson string = '[]'
param enableHostedAgents bool = true
param enableCapabilityHost bool = true
param enableMonitoring bool = true
param useExistingAiProject bool = false
param principalId string
param principalType string

// Container Apps parameters
param backendImageName string = ''
param frontendImageName string = ''

// Optional existing shared resources
param existingContainerRegistryResourceId string = ''
param existingContainerRegistryEndpoint string = ''
param existingAcrConnectionName string = ''
param existingApplicationInsightsConnectionString string = ''
param existingApplicationInsightsResourceId string = ''
param existingAppInsightsConnectionName string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var tags = {
  'azd-env-name': environmentName
}

var aiProjectDeployments = json(aiProjectDeploymentsJson)
var aiProjectConnections = json(aiProjectConnectionsJson)
var aiProjectConnectionCredentials = empty(aiProjectConnectionCredentialsJson) ? {} : json(aiProjectConnectionCredentialsJson)
var aiProjectDependentResources = json(aiProjectDependentResourcesJson)

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module monitoring './core/monitoring.bicep' = if (enableMonitoring && empty(existingApplicationInsightsConnectionString)) {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${environmentName}'
    applicationInsightsName: '${abbrs.insightsComponents}${environmentName}'
  }
}

module containerRegistry './core/container-registry.bicep' = if (empty(existingContainerRegistryResourceId)) {
  name: 'container-registry'
  scope: rg
  params: {
    location: location
    tags: tags
    name: '${abbrs.containerRegistryRegistries}${replace(environmentName, '-', '')}'
  }
}

var effectiveApplicationInsightsConnectionString = !empty(existingApplicationInsightsConnectionString) ? existingApplicationInsightsConnectionString : (enableMonitoring && empty(existingApplicationInsightsConnectionString) ? monitoring!.outputs.applicationInsightsConnectionString : '')
var effectiveApplicationInsightsResourceId = !empty(existingApplicationInsightsResourceId) ? existingApplicationInsightsResourceId : (enableMonitoring && empty(existingApplicationInsightsConnectionString) ? monitoring!.outputs.applicationInsightsId : '')
var effectiveContainerRegistryResourceId = !empty(existingContainerRegistryResourceId) ? existingContainerRegistryResourceId : containerRegistry!.outputs.id
var effectiveContainerRegistryEndpoint = !empty(existingContainerRegistryEndpoint) ? existingContainerRegistryEndpoint : containerRegistry!.outputs.loginServer
var existingContainerRegistryName = !empty(existingContainerRegistryResourceId) ? last(split(existingContainerRegistryResourceId, '/')) : ''
var existingContainerRegistryResourceGroup = !empty(existingContainerRegistryResourceId) ? split(existingContainerRegistryResourceId, '/')[4] : ''
var effectiveContainerRegistryName = !empty(existingContainerRegistryResourceId) ? existingContainerRegistryName : containerRegistry!.outputs.name

module aiFoundry './core/ai-foundry.bicep' = {
  name: 'ai-foundry'
  scope: rg
  params: {
    location: location
    tags: tags
    aiFoundryResourceName: !empty(aiFoundryResourceName) ? aiFoundryResourceName : '${abbrs.cognitiveServicesAccounts}${environmentName}'
    aiFoundryProjectName: aiFoundryProjectName
    deployments: aiProjectDeployments
    connections: aiProjectConnections
    connectionCredentials: aiProjectConnectionCredentials
    dependentResources: aiProjectDependentResources
    enableHostedAgents: enableHostedAgents
    enableCapabilityHost: enableCapabilityHost
    enableMonitoring: enableMonitoring
    useExistingAiProject: useExistingAiProject
    principalId: principalId
    principalType: principalType
    containerRegistryResourceId: effectiveContainerRegistryResourceId
    containerRegistryEndpoint: effectiveContainerRegistryEndpoint
    acrConnectionName: existingAcrConnectionName
    applicationInsightsConnectionString: effectiveApplicationInsightsConnectionString
    applicationInsightsResourceId: effectiveApplicationInsightsResourceId
    applicationInsightsConnectionName: existingAppInsightsConnectionName
  }
}

module containerAppsEnv './core/container-apps-environment.bicep' = {
  name: 'container-apps-env'
  scope: rg
  params: {
    location: location
    tags: tags
    name: '${abbrs.appManagedEnvironments}${environmentName}'
    logAnalyticsWorkspaceId: enableMonitoring && empty(existingApplicationInsightsConnectionString) ? monitoring!.outputs.logAnalyticsWorkspaceId : ''
  }
}

var backendEnv = concat([
  {
    name: 'BACKEND_HOST'
    value: '0.0.0.0'
  }
  {
    name: 'BACKEND_PORT'
    value: '8000'
  }
  {
    name: 'EXECUTION_MODE'
    value: 'agent_distributed'
  }
  {
    name: 'FOUNDRY_PROJECT_ENDPOINT'
    value: aiFoundry.outputs.projectEndpoint
  }
], !empty(effectiveApplicationInsightsConnectionString) ? [
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: effectiveApplicationInsightsConnectionString
  }
] : [])

module backendApi './core/container-app.bicep' = {
  name: 'backend-api'
  scope: rg
  params: {
    name: 'backend-api'
    location: location
    tags: union(tags, {
      'azd-service-name': 'backend-api'
    })
    containerAppsEnvironmentId: containerAppsEnv.outputs.id
    containerRegistryServer: effectiveContainerRegistryEndpoint
    imageName: backendImageName
    targetPort: 8000
    external: false
    env: backendEnv
  }
}

var frontendEnv = concat([
  {
    name: 'FRONTEND_HOST'
    value: '0.0.0.0'
  }
  {
    name: 'FRONTEND_PORT'
    value: '3000'
  }
  {
    name: 'BACKEND_BASE_URL'
    value: 'https://${backendApi.outputs.fqdn}'
  }
], !empty(effectiveApplicationInsightsConnectionString) ? [
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: effectiveApplicationInsightsConnectionString
  }
] : [])

module frontend './core/container-app.bicep' = {
  name: 'frontend'
  scope: rg
  params: {
    name: 'frontend'
    location: location
    tags: union(tags, {
      'azd-service-name': 'frontend'
    })
    containerAppsEnvironmentId: containerAppsEnv.outputs.id
    containerRegistryServer: effectiveContainerRegistryEndpoint
    imageName: frontendImageName
    targetPort: 3000
    external: true
    env: frontendEnv
  }
}

module backendAcrPull './core/acr-pull-role-assignment.bicep' = if (empty(existingContainerRegistryResourceId)) {
  name: 'backend-acr-pull'
  scope: rg
  params: {
    acrName: containerRegistry!.outputs.name
    acrResourceId: containerRegistry!.outputs.id
    principalId: backendApi.outputs.principalId
  }
}

module backendAcrPullExisting './core/acr-pull-role-assignment.bicep' = if (!empty(existingContainerRegistryResourceId)) {
  name: 'backend-acr-pull-existing'
  scope: resourceGroup(existingContainerRegistryResourceGroup)
  params: {
    acrName: existingContainerRegistryName
    acrResourceId: existingContainerRegistryResourceId
    principalId: backendApi.outputs.principalId
  }
}

module frontendAcrPull './core/acr-pull-role-assignment.bicep' = if (empty(existingContainerRegistryResourceId)) {
  name: 'frontend-acr-pull'
  scope: rg
  params: {
    acrName: containerRegistry!.outputs.name
    acrResourceId: containerRegistry!.outputs.id
    principalId: frontend.outputs.principalId
  }
}

module frontendAcrPullExisting './core/acr-pull-role-assignment.bicep' = if (!empty(existingContainerRegistryResourceId)) {
  name: 'frontend-acr-pull-existing'
  scope: resourceGroup(existingContainerRegistryResourceGroup)
  params: {
    acrName: existingContainerRegistryName
    acrResourceId: existingContainerRegistryResourceId
    principalId: frontend.outputs.principalId
  }
}

module foundryAcrPull './core/acr-pull-role-assignment.bicep' = if (enableHostedAgents && !useExistingAiProject && empty(existingContainerRegistryResourceId)) {
  name: 'foundry-acr-pull'
  scope: rg
  params: {
    acrName: containerRegistry!.outputs.name
    acrResourceId: containerRegistry!.outputs.id
    principalId: aiFoundry.outputs.projectPrincipalId
  }
}

module foundryAcrPullExisting './core/acr-pull-role-assignment.bicep' = if (enableHostedAgents && !useExistingAiProject && !empty(existingContainerRegistryResourceId)) {
  name: 'foundry-acr-pull-existing'
  scope: resourceGroup(existingContainerRegistryResourceGroup)
  params: {
    acrName: existingContainerRegistryName
    acrResourceId: existingContainerRegistryResourceId
    principalId: aiFoundry.outputs.projectPrincipalId
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroupName
output AZURE_CONTAINER_REGISTRY string = effectiveContainerRegistryName
output AZURE_CONTAINER_REGISTRY_NAME string = effectiveContainerRegistryName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = effectiveContainerRegistryEndpoint
output AZURE_AI_ACCOUNT_ID string = aiFoundry.outputs.accountId
output AZURE_AI_PROJECT_ID string = aiFoundry.outputs.projectId
output AZURE_AI_FOUNDRY_PROJECT_ID string = aiFoundry.outputs.projectId
output AZURE_AI_ACCOUNT_NAME string = aiFoundry.outputs.accountName
output AZURE_AI_PROJECT_NAME string = aiFoundry.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = aiFoundry.outputs.projectEndpoint
output AI_FOUNDRY_PROJECT_ENDPOINT string = aiFoundry.outputs.projectEndpoint
output AZURE_OPENAI_ENDPOINT string = aiFoundry.outputs.openAiEndpoint
output AZURE_AI_PROJECT_ACR_CONNECTION_NAME string = aiFoundry.outputs.acrConnectionName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = effectiveApplicationInsightsConnectionString
output APPLICATIONINSIGHTS_RESOURCE_ID string = effectiveApplicationInsightsResourceId
output APPLICATIONINSIGHTS_CONNECTION_NAME string = aiFoundry.outputs.applicationInsightsConnectionName
output BACKEND_URI string = backendApi.outputs.uri
output FRONTEND_URI string = frontend.outputs.uri
