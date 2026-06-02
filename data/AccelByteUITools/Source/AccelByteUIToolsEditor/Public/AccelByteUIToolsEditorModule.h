// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "HttpRouteHandle.h"
#include "Modules/ModuleManager.h"

class IHttpRouter;

class FAccelByteUIToolsEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;

private:
	void StartHttpBridge();
	void StopHttpBridge();

	TSharedPtr<IHttpRouter> Router;
	FHttpRouteHandle HealthRouteHandle;
	FHttpRouteHandle GenerateRouteHandle;
	FHttpRouteHandle ResolveRouteHandle;
	FHttpRouteHandle PatchRouteHandle;
	FHttpRouteHandle LiveCodingCompileRouteHandle;
};
