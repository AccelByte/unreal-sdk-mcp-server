// Copyright (c) 2026 AccelByte Inc. All Rights Reserved.

#pragma once

#include "Modules/ModuleManager.h"

class FWidgetBlueprintGeneratorEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
