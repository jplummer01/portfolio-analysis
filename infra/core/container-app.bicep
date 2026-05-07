param name string
param location string
param tags object = {}
param containerAppsEnvironmentId string
param containerRegistryServer string = ''
param imageName string = ''
param targetPort int
param external bool = false
param env array = []

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
      }
      registries: !empty(containerRegistryServer) ? [
        {
          server: containerRegistryServer
          identity: 'system'
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: name
          image: !empty(imageName) ? imageName : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          env: env
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output name string = app.name
output id string = app.id
output principalId string = app.identity.principalId
